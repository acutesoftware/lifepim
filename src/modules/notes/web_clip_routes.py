"""Webpage drafts and atomic persistence into the ordinary Notes/Places tables."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import shutil
import threading
import time

from flask import current_app, jsonify, render_template, request, session, url_for, abort
from common import data, settings, areas, links, note_search_index
from common.utils import get_tabs, get_side_tabs, lg_usr
from modules.notes import web_clip as clip

# Short-lived previews are not Notes and contain no filesystem paths supplied by clients.
# A process restart discards them; Cancel and successful Save discard them immediately.
_drafts = {}
_lock = threading.RLock()
_TTL = 3600


def _owner():
    from modules.notes.routes import _current_owner_user_id
    if 'web_clip_session' not in session:
        session['web_clip_session'] = secrets.token_urlsafe(24)
    return (str(data._get_conn().execute('PRAGMA database_list').fetchone()[2]),
            _current_owner_user_id(), session['web_clip_session'])


def _cleanup():
    now = time.monotonic()
    for token in list(_drafts):
        if now - _drafts[token]['created'] > _TTL and not _drafts[token].get('saving'):
            del _drafts[token]


def _draft(token):
    _cleanup()
    draft = _drafts.get(token)
    if not draft or draft['owner'] != _owner():
        raise clip.WebClipError("This webpage preview has expired. Fetch the page again.")
    return draft


def _default_target():
    from modules.notes import routes
    conn = data._get_conn()
    area_id = settings.get_setting('general.default_area', '', conn=conn).strip()
    if not area_id or not areas.area_get(area_id, owner_user_id=routes._current_owner_user_id()):
        raise clip.WebClipError("No default Area is configured. Set a default Area in Settings > General before saving this webpage.")
    folder = areas.area_default_folder_get(area_id, owner_user_id=routes._current_owner_user_id())
    if not folder:
        raise clip.WebClipError("The default Area has no default Notes folder. Set one in its Folders panel.")
    return routes._note_create_target_folder(area_id, folder)


def _insert(conn, table, values):
    # Use the existing table schema, including ownership and standard audit fields.
    columns = {r[1] for r in conn.execute(f'PRAGMA table_info({table})')}
    values = {k: v for k, v in values.items() if k in columns}
    return conn.execute(f"INSERT INTO {table} ({', '.join(values)}) VALUES ({', '.join('?' for _ in values)})",
                        list(values.values())).lastrowid


def save_clip(result, title, content):
    from modules.notes import routes
    folder, area_id = _default_target()
    conn = data._get_conn()
    # Schema helpers commit; run all of them before the save transaction.
    data.ensure_notes_schema(conn)
    data.ensure_places_schema(conn)
    data.ensure_folder_schema(conn)
    links.ensure_links_schema(conn)
    target = Path(folder)
    target.mkdir(parents=True, exist_ok=True)
    max_length = min(210, 240 - len(str(target)) - 24) if os.name == 'nt' else 210
    suggested = clip.filename_for(result, max_length=max_length)
    note_path = None
    assets = None
    archive_path = None
    owned_paths = []
    try:
        # Reserve the name exclusively; never overwrite notes, archives or assets.
        for number in range(1, 10000):
            suffix = '' if number == 1 else f'_{number:02d}'
            candidate = target / f'{Path(suggested).stem}{suffix}.md'
            assets = candidate.with_suffix('.assets')
            archive_path = candidate.with_suffix('.archive.html')
            if assets.exists() or archive_path.exists():
                continue
            try:
                routes._write_note_file(str(target), candidate.name, '')
                note_path = candidate
                owned_paths.append(note_path)
                break
            except FileExistsError:
                continue
        if note_path is None:
            raise clip.WebClipError("Could not find an available filename for this webpage.")
        markdown, warnings = content, []
        if result.images:
            try:
                # Reserve assets so cleanup only removes our own directory.
                assets.mkdir()
                owned_paths.append(assets)
                markdown, warnings = clip.download_images(content, result, assets)
                if not any(assets.iterdir()):
                    assets.rmdir()
                    owned_paths.remove(assets)
            except Exception:
                current_app.logger.exception('Web clip image preservation failed')
                warnings.append('Article images could not be saved locally; original references were kept.')
                markdown = content
        if result.html:
            with archive_path.open('x', encoding='utf-8') as handle:
                owned_paths.append(archive_path)
                handle.write(result.html)
            markdown += f'\n\nArchived copy: [{archive_path.name}]({archive_path.name})\n'
        routes._write_note_file_content(str(note_path), markdown)
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        owner = routes._current_owner_user_id()
        common = {'owner_user_id': owner, 'user_name': data._current_user(), 'rec_extract_date': now, 'area': area_id}
        # Existing generic record helpers commit individually. Keep these related inserts
        # in one transaction, so a failure cannot leave a Note, Place or link on its own.
        conn.execute('BEGIN IMMEDIATE')
        place_id = None
        place_columns = {r[1] for r in conn.execute('PRAGMA table_info(lp_places)')}
        where = "place_type = 'url'"
        params = []
        if 'owner_user_id' in place_columns:
            where += ' AND owner_user_id IS ?'
            params.append(owner)
        for row in conn.execute(f'SELECT id, name, url FROM lp_places WHERE {where}', params):
            try:
                matches = clip.url_key(row['url']) == clip.url_key(result.source_url)
            except clip.WebClipError:
                matches = False
            if matches:
                place_id = row['id']
                if not (row['name'] or '').strip():
                    conn.execute('UPDATE lp_places SET name = ? WHERE id = ?', (title, place_id))
                break
        if place_id is None:
            place_id = _insert(conn, 'lp_places', {**common, 'place_type': 'url', 'name': title, 'url': result.source_url})
        metadata = {'source_type': 'webpage', 'source_url': result.source_url,
                    'source_final_url': result.final_url, 'source_place_id': place_id,
                    'web_capture_method': result.method_used, 'web_capture_date': result.captured,
                    'web_author': result.author, 'web_published_date': result.published_date,
                    'web_archive_path': archive_path.name if result.html else ''}
        note_id = _insert(conn, 'lp_notes', {**common, 'file_name': note_path.name, 'path': str(target),
                          'folder_id': routes._upsert_note_dim_folder(conn, str(target)),
                          'title': title, 'size': str(note_path.stat().st_size), 'date_created': now,
                          'date_modified': datetime.fromtimestamp(note_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                          'color': routes.DEFAULT_NOTE_COLOR, 'is_template': 'false', 'is_important': 'false',
                          'capture_metadata': json.dumps(metadata)})
        conn.execute("INSERT INTO lp_links (src_type, src_id, dst_type, dst_id, link_type, created_utc, created_by) "
                     "VALUES ('note', ?, 'place', ?, 'related', ?, 'webpage')", (str(note_id), str(place_id), now))
        conn.commit()
    except Exception:
        conn.rollback()
        for path in reversed(owned_paths):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
        raise
    # Auxiliary indexing must not turn an already committed save into a reported failure.
    try:
        note_search_index.upsert_note(note_id, str(note_path), title=title, content=markdown, conn=conn)
        routes._sync_note_links(note_id, markdown)
        lg_usr(action='WEB_CLIP_SAVE_SUCCESS', entity_type='lp_notes', entity_id=note_id,
               extra={**metadata, 'characters': len(markdown), 'warnings': warnings}, conn=conn)
    except Exception:
        current_app.logger.exception('Web clip auxiliary indexing/logging failed')
    return {'note_id': note_id, 'file_name': note_path.name, 'place_id': place_id, 'warnings': warnings}


def register(bp):
    @bp.route('/web', methods=['GET'])
    def web_clip_page():
        return render_template('note_web_fetch.html', active_tab='notes', tabs=get_tabs(),
                               side_tabs=get_side_tabs(), methods=clip.METHOD_LABELS,
                               content_title='New Note from Webpage')

    @bp.route('/api/web/fetch', methods=['POST'])
    def web_clip_fetch():
        payload = request.get_json(silent=True) or {}
        try:
            url = clip.validate_url(payload.get('url', ''))
            lg_usr(action='WEB_CLIP_FETCH_STARTED', entity_type='lp_notes',
                   extra={'url': url, 'method': payload.get('method', 0)}, conn=data._get_conn())
            result = clip.fetch_web_note(url, payload.get('method', 0))
            if not result.success:
                return jsonify(success=False, error='The webpage could not be extracted.', warnings=result.warnings), 422
            with _lock:
                _cleanup()
                if len(_drafts) >= 16:
                    raise clip.WebClipError('Too many open webpage previews. Cancel an existing preview first.')
                token = secrets.token_urlsafe(32)
                _drafts[token] = {'owner': _owner(), 'result': result, 'created': time.monotonic()}
            lg_usr(action='WEB_CLIP_EXTRACT_SUCCESS', entity_type='lp_notes',
                   extra={'url': url, 'method': result.method_used, 'characters': len(result.markdown),
                          'images': len(result.images), 'warnings': result.warnings}, conn=data._get_conn())
            return jsonify(success=True, token=token, method_used=result.method_used,
                           title=result.title, markdown=result.markdown, author=result.author,
                           published_date=result.published_date, site=result.site_name,
                           suggested_filename=clip.filename_for(result), warnings=result.warnings,
                           open_url=url_for('notes.web_clip_preview', token=token))
        except clip.WebClipError as exc:
            return jsonify(error=str(exc)), 400
        except Exception:
            current_app.logger.exception('WEB_CLIP_FETCH_FAILED')
            return jsonify(error='Could not fetch webpage. Please try again.'), 500

    @bp.route('/web/preview/<token>')
    def web_clip_preview(token):
        with _lock:
            try:
                draft = _draft(token)
            except clip.WebClipError:
                abort(404)
            result = draft['result']
        return render_template('note_edit.html', active_tab='notes', tabs=get_tabs(), side_tabs=get_side_tabs(),
                               content_title='New Note from Webpage', web_clip=result, web_token=token,
                               web_filename=clip.filename_for(result), web_method=clip.METHOD_LABELS[result.method_used],
                               note_text=result.markdown, note=None)

    @bp.route('/api/web/cancel/<token>', methods=['POST'])
    def web_clip_cancel(token):
        with _lock:
            try:
                draft = _draft(token)
                if draft.get('saving'):
                    return jsonify(error='This webpage is being saved.'), 409
                del _drafts[token]
            except clip.WebClipError:
                pass
        return jsonify(success=True)

    @bp.route('/api/web/render/<token>', methods=['POST'])
    def web_clip_render(token):
        from utils import markdown_utils
        with _lock:
            try:
                _draft(token)
            except clip.WebClipError as exc:
                return jsonify(error=str(exc)), 400
        content = (request.get_json(silent=True) or {}).get('content', '')
        if not isinstance(content, str) or len(content) > MAX_CONTENT:
            return jsonify(error='The note content is too large.'), 400
        from lxml_html_clean import Cleaner
        rendered = markdown_utils.render_markdown(content, allow_html=False)
        return jsonify(html=Cleaner().clean_html(rendered) if rendered else '')

    @bp.route('/api/web/save/<token>', methods=['POST'])
    def web_clip_save(token):
        payload = request.get_json(silent=True) or {}
        draft = None
        try:
            title, content = payload.get('title'), payload.get('content')
            if not isinstance(title, str) or not title.strip() or len(title) > 1000:
                raise clip.WebClipError('Enter a page title (up to 1000 characters).')
            if not isinstance(content, str) or len(content) > MAX_CONTENT:
                raise clip.WebClipError('The note content is missing or too large.')
            with _lock:
                draft = _draft(token)
                if draft.get('saving'):
                    return jsonify(error='This webpage is already being saved.'), 409
                draft['saving'] = True
            created = save_clip(draft['result'], title.strip(), content)
            with _lock:
                _drafts.pop(token, None)
            return jsonify(**created, open_url=url_for('notes.edit_note_route', note_id=created['note_id']))
        except clip.WebClipError as exc:
            return jsonify(error=str(exc)), 400
        except Exception:
            current_app.logger.exception('WEB_CLIP_SAVE_FAILED')
            return jsonify(error='Could not save webpage. Check the default folder and try again.'), 500
        finally:
            if draft:
                with _lock:
                    draft['saving'] = False


MAX_CONTENT = 4 * 1024 * 1024
