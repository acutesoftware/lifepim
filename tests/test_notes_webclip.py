from io import BytesIO
import json
import os
from pathlib import Path
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import test_note_creation as fixtures
from common import settings, areas
from modules.notes import web_clip as clip, web_clip_routes as web

ARTICLE = '''<html><head><title>Keeping old files readable</title></head><body>
<header>Advertisement: BUY NOW</header><nav>Home Contact Sign in Subscribe</nav>
<article><h1>Keeping old files readable</h1>
<p>Keeping digital documents readable over many years requires careful planning. Open formats
help people move their writing between applications without losing access to their work.</p>
<p>Regular backups and simple files make this easier. Store descriptive filenames alongside
the original source and check that the copies can still be opened on another computer.</p>
<h2>Practical steps</h2><ul><li>Keep a backup</li><li>Use open formats</li></ul>
<p>Read <a href="/guide">the preservation guide</a> for practical examples.</p></article>
<footer>Privacy policy Contact Advertising</footer></body></html>'''


def result(method=1):
    return clip.WebClipResult(success=True, method_used=method, source_url='https://www.example.com/article',
                              final_url='https://example.com/article', title='This is a Very Long: Page / Name?',
                              markdown='# Article\n\nUseful content.\n\nSource: https://www.example.com/article\n',
                              captured='2026-09-06T12:00:00')


class TestExtraction(unittest.TestCase):
    def test_filename(self):
        self.assertEqual(clip.filename_for(result()), 'web_snip_example_com_this_is_a_very_long_page_name_20260906.md')
        value = result()
        value.title = 'long description ' * 100
        name = clip.filename_for(value)
        self.assertLessEqual(len(name), 220)
        self.assertTrue(name.endswith('_20260906.md'))

    def test_reader_fixture(self):
        value = clip.extract_html(ARTICLE, 'http://localhost/article', 1)
        self.assertTrue(value.success)
        self.assertIn('digital documents', value.markdown)
        self.assertIn('http://localhost/guide', value.markdown)
        self.assertNotIn('BUY NOW', value.markdown)
        self.assertNotIn('Privacy policy', value.markdown)

    def test_recipe_jsonld_retains_ingredients_and_collapsed_steps(self):
        recipe = {'@type': ['CreativeWork', 'Recipe'], 'name': 'Toast & herbs',
                  'author': {'@type': 'Person', 'name': 'Example Cook'}, 'prepTime': 'PT5M',
                  'image': [{'@type': 'ImageObject', 'url': '/toast.jpg'}],
                  'recipeIngredient': ['2 slices of bread', '1 spoon of herbs'],
                  'recipeInstructions': [{'@type': 'HowToSection', 'name': 'Prepare', 'itemListElement': [
                      {'@type': 'HowToStep', 'text': 'Toast the bread.'},
                      {'@type': 'HowToStep', 'text': '<p>Sprinkle the herbs over the warm toast.</p>'}]}]}
        html = '<html><title>Toast &amp; herbs</title><script type="application/ld+json">' + json.dumps({'@graph': [recipe]}) + '</script><article><p>A short preview.</p><a href="#">Read more</a><div hidden>Other content</div></article></html>'
        for method in (1, 2, 4):
            value = clip.extract_html(html, 'https://example.com/recipe', method)
            self.assertTrue(value.success)
            self.assertEqual(value.title, 'Toast & herbs')
            self.assertIn('## Ingredients\n\n- 2 slices of bread\n- 1 spoon of herbs', value.markdown)
            self.assertIn('2. Sprinkle the herbs over the warm toast.', value.markdown)
            self.assertIn('### Prepare', value.markdown)
            self.assertIn('Prep time: 5 min', value.markdown)
            self.assertEqual(value.images, ['https://example.com/toast.jpg'])

    def test_incomplete_recipe_does_not_replace_valid_article(self):
        for script in ['{invalid json', json.dumps({'@type': 'Recipe', 'name': 'Incomplete', 'recipeIngredient': ['bread']})]:
            html = ARTICLE.replace('<body>', '<body><script type="application/ld+json">' + script + '</script>')
            value = clip.extract_html(html, 'https://example.com/', 1)
            self.assertTrue(value.success)
            self.assertIn('digital documents', value.markdown)
            self.assertNotIn('## Ingredients', value.markdown)

    def test_short_structured_page_and_boilerplate(self):
        self.assertTrue(clip.is_web_content_useful('This short article explains how to store plain text documents safely for many years.', 'Short article', True))
        self.assertFalse(clip.is_web_content_useful('Sign in Accept cookies Subscribe Privacy policy ' * 5, 'Menu', True))

    def test_auto_order_and_explicit_methods(self):
        for requested, success_at, expected in [(0, 4, [1, 2, 4]), (0, 2, [1, 2]), (0, 1, [1]),
                                                (1, 1, [1]), (2, 2, [2]), (4, 4, [4])]:
            calls = []
            def adapter(method):
                def run(url):
                    calls.append(method)
                    value = result(method)
                    value.success = method == success_at
                    if not value.success:
                        value.warnings = [f'Method {method} failed']
                    return value
                return run
            with patch.object(clip, 'extract_reader', adapter(1)), patch.object(clip, 'extract_rendered', adapter(2)), patch.object(clip, 'archive_webpage', adapter(4)):
                value = clip.fetch_web_note('http://localhost/article', requested)
            self.assertEqual(calls, expected)
            self.assertTrue(value.success)
            self.assertEqual(len(value.warnings), len(expected) - 1)

    def test_missing_optional_support_continues(self):
        with patch.object(clip, 'extract_reader', side_effect=clip.WebClipError('Insufficient content')), patch.object(clip, 'extract_rendered', side_effect=clip.WebClipError('Not installed')), patch.object(clip, 'archive_webpage', return_value=result(4)):
            value = clip.fetch_web_note('http://localhost/')
        self.assertTrue(value.success)
        self.assertEqual(len(value.warnings), 2)

    def test_validation(self):
        for url in ['file:///tmp/x', 'ftp://host', 'javascript:alert(1)', 'data:text/html,x', 'https://', 'http://host:bad']:
            with self.assertRaises(clip.WebClipError):
                clip.validate_url(url)
        self.assertEqual(clip.validate_url('http://192.168.1.2/'), 'http://192.168.1.2/')
        for method in [3, '1', None, True]:
            with self.assertRaises(clip.WebClipError):
                clip.fetch_web_note('http://localhost/', method)

    def test_url_comparison_keeps_query_and_path_case(self):
        self.assertEqual(clip.url_key('https://EXAMPLE.com/a/#one'), clip.url_key('https://example.com/a'))
        self.assertNotEqual(clip.url_key('https://example.com/A?q=1'), clip.url_key('https://example.com/a?q=1'))
        self.assertNotEqual(clip.url_key('https://example.com/a?q=1'), clip.url_key('https://example.com/a?q=2'))

    def test_archive_keeps_snapshot_when_extraction_fails(self):
        output_paths = []
        def archive(command, **kwargs):
            self.assertEqual(command[command.index('--browser-wait-until') + 1], 'domContentLoaded')
            load = int(command[command.index('--browser-load-max-time') + 1])
            capture = int(command[command.index('--browser-capture-max-time') + 1])
            self.assertLess(load + capture + 1500, clip.ARCHIVE_PROCESS_SECONDS * 1000)
            self.assertEqual(command[command.index('--browser-single-process') + 1], 'false')
            self.assertEqual(command[command.index('--remove-frames') + 1], 'true')
            self.assertEqual(command[command.index('--load-deferred-images') + 1], 'false')
            output = Path(command[-1])
            output_paths.append(output)
            output.write_text('<html><title>Snapshot</title><body>Short</body></html>', encoding='utf-8')
        with patch.object(clip, '_archive_browser_args', return_value=[]), patch.object(clip.shutil, 'which', return_value='single-file.exe'), patch.object(clip, '_run_archive', side_effect=archive):
            value = clip.archive_webpage('http://localhost/')
        self.assertTrue(value.success)
        self.assertIn('could not be automatically extracted', value.markdown)
        self.assertTrue(value.html)
        self.assertFalse(output_paths[0].exists())

    @unittest.skipUnless(os.environ.get('LIFEPIM_TEST_BROWSER') == '1', 'Set LIFEPIM_TEST_BROWSER=1 with Playwright Chromium installed')
    def test_local_javascript_page(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(('<html><head><title>Loading</title></head><body><script>setTimeout(() => { document.documentElement.innerHTML = ' + json.dumps(ARTICLE) + '; }, 100);</script></body></html>').encode())
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}/'
            self.assertFalse(clip.extract_reader(url).success)
            self.assertTrue(clip.extract_rendered(url).success)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


class TestWebSave(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.TestNoteCreation()
        self.fixture.setUp()
        self.conn = self.fixture.conn
        self.target = Path(self.fixture.tmpdir.name) / 'notes'
        self.app = self.fixture._notes_test_app()
        self.app.secret_key = 'tests-only'
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        areas.area_upsert({'area_id': 'test/web', 'tab': 'TEST', 'group_name': 'Test', 'area_name': 'Web'}, conn=self.conn)
        areas.area_folder_add('test/web', str(self.target), folder_role='default', is_write_enabled=1, conn=self.conn)
        settings.save_general_settings({'default_area': 'test/web'}, self.conn)

    def tearDown(self):
        web._drafts.clear()
        self.fixture.tearDown()

    def fetch(self, value=None):
        with patch.object(clip, 'fetch_web_note', return_value=value or result()):
            response = self.client.post('/notes/api/web/fetch', json={'url': 'https://www.example.com/article', 'method': 0})
        self.assertEqual(response.status_code, 200, response.data)
        return response.get_json()

    def save(self, draft, **kwargs):
        return self.client.post('/notes/api/web/save/' + draft['token'], json={'title': 'Edited title', 'content': 'Edited content', **kwargs})

    def test_fetch_preview_cancel_no_persistence(self):
        draft = self.fetch()
        with patch.object(web, 'get_tabs', return_value=[]), patch.object(web, 'get_side_tabs', return_value=[]):
            response = self.client.get(draft['open_url'])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn(b'data-web-draft="true"', response.data)
        self.assertIn(b'id="note-editor"', response.data)
        self.assertEqual(self.client.post('/notes/api/web/cancel/' + draft['token']).status_code, 200)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM lp_notes').fetchone()[0], 0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM lp_places').fetchone()[0], 0)
        self.assertFalse(self.target.exists())

    def test_explicit_failure_reports_method_without_falling_back(self):
        for method, adapter in [(1, 'extract_reader'), (2, 'extract_rendered'), (4, 'archive_webpage')]:
            with patch.object(clip, adapter, side_effect=clip.WebClipError('Controlled failure')) as selected:
                response = self.client.post('/notes/api/web/fetch', json={'url': 'https://example.com/', 'method': method})
            self.assertEqual(response.status_code, 422)
            self.assertEqual(selected.call_count, 1)
            self.assertEqual(response.json['method_requested'], method)
            self.assertEqual(response.json['method_used'], method)
            self.assertIn(clip.METHOD_LABELS[method], response.json['error'])
            self.assertEqual(response.json['warnings'], ['Controlled failure'])

    def test_save_duplicate_place_collision_archive_and_metadata(self):
        value = result(4)
        value.html = '<html><body>Archived</body></html>'
        first = self.save(self.fetch(value))
        self.assertEqual(first.status_code, 200, first.data)
        original = first.get_json()
        self.conn.execute("UPDATE lp_places SET name = 'Personal title'")
        self.conn.commit()
        second = self.save(self.fetch(value))
        self.assertEqual(second.status_code, 200, second.data)
        self.assertTrue(second.get_json()['file_name'].endswith('_02.md'))
        third = self.save(self.fetch(value)).get_json()
        self.assertTrue(third['file_name'].endswith('_03.md'))
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM lp_places').fetchone()[0], 1)
        self.assertEqual(self.conn.execute('SELECT name FROM lp_places').fetchone()[0], 'Personal title')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM lp_links').fetchone()[0], 3)
        row = self.conn.execute('SELECT * FROM lp_notes WHERE id = ?', (original['note_id'],)).fetchone()
        metadata = json.loads(row['capture_metadata'])
        self.assertEqual(metadata['web_capture_method'], 4)
        self.assertEqual(metadata['source_url'], value.source_url)
        path = self.target / row['file_name']
        self.assertTrue(path.with_suffix('.archive.html').exists())
        self.assertIn('Edited content', path.read_text(encoding='utf-8'))
        self.assertIn(path.with_suffix('.archive.html').name, path.read_text(encoding='utf-8'))
        self.assertFalse(path.read_text(encoding='utf-8').startswith('---'))

    def test_missing_default_keeps_preview_and_creates_nothing(self):
        settings.save_general_settings({'default_area': ''}, self.conn)
        draft = self.fetch()
        response = self.save(draft)
        self.assertEqual(response.status_code, 400)
        self.assertIn('default Area', response.get_json()['error'])
        self.assertIn(draft['token'], web._drafts)
        self.assertFalse(self.target.exists())

    def test_folder_sync_preserves_saved_title_and_provenance(self):
        from modules.notes import routes
        created = self.save(self.fetch()).get_json()
        before = self.conn.execute('SELECT capture_metadata FROM lp_notes WHERE id = ?', (created['note_id'],)).fetchone()[0]
        routes._sync_note_rows(str(self.target))
        row = self.conn.execute('SELECT title, capture_metadata FROM lp_notes WHERE id = ?', (created['note_id'],)).fetchone()
        self.assertEqual(row['title'], 'Edited title')
        self.assertEqual(row['capture_metadata'], before)

    def test_preview_sanitizes_script_links(self):
        draft = self.fetch()
        response = self.client.post('/notes/api/web/render/' + draft['token'], json={
            'content': '[bad](javascript:alert(1))\n<script>alert(2)</script>'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('javascript:', response.get_json()['html'])
        self.assertNotIn('<script>', response.get_json()['html'])

    def test_archive_link_rendering_and_isolation(self):
        from utils import markdown_utils
        from modules.notes import routes
        value = result(4)
        value.html = '<html><script>bad()</script><body>Archived</body></html>'
        created = self.save(self.fetch(value)).get_json()
        archive = Path(created['file_name']).with_suffix('.archive.html').name
        html = markdown_utils.render_markdown(f'[Archived copy]({archive})', asset_resolver=lambda name: '/asset/' + name)
        self.assertIn('/asset/' + archive, html)
        with patch.object(routes.security, 'can_view_note', return_value=True):
            response = self.client.get(f"/notes/asset/{created['note_id']}/{archive}")
        self.assertEqual(response.status_code, 200)
        self.assertIn('sandbox', response.headers['Content-Security-Policy'])
        response.close()

    @unittest.skipUnless(os.environ.get('LIFEPIM_TEST_BROWSER') == '1', 'Set LIFEPIM_TEST_BROWSER=1 with Playwright Chromium installed')
    def test_browser_fetch_edit_save_and_cancel(self):
        import sqlite3
        from werkzeug.serving import make_server
        from playwright.sync_api import sync_playwright
        from common import data
        from modules.notes import routes
        shared = sqlite3.connect(':memory:', check_same_thread=False)
        shared.row_factory = sqlite3.Row
        self.conn.backup(shared)
        self.conn.close()
        self.conn = self.fixture.conn = data.conn = shared
        self.app.static_folder = str(Path(__file__).resolve().parents[1] / 'src/static')
        server = make_server('127.0.0.1', 0, self.app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        release_archive = threading.Event()
        try:
            requested_methods = []
            def fake_fetch(url, method):
                requested_methods.append(method)
                if method == 4:
                    release_archive.wait(8)
                return result(method)
            with patch.object(clip, 'fetch_web_note', side_effect=fake_fetch), patch.object(web, 'get_tabs', return_value=[]), patch.object(web, 'get_side_tabs', return_value=[]), patch.object(routes.security, 'can_edit_note', return_value=True):
                with sync_playwright() as pw:
                    browser = pw.chromium.launch()
                    page = browser.new_page()
                    dialogs = []
                    def dialog_handler(dialog):
                        dialogs.append(dialog.type)
                        dialog.dismiss()
                    page.on('dialog', dialog_handler)
                    origin = f'http://127.0.0.1:{server.server_port}'
                    page.goto(origin + '/notes/web', wait_until='domcontentloaded')
                    self.assertIn('?v=', page.locator('script[src*="note_web_fetch.js"]').get_attribute('src'))
                    # A proxy/HTML error must clear the busy state rather than leave
                    # an apparently completed browser tab with a stuck fetch message.
                    page.route('**/notes/api/web/fetch', lambda route: route.fulfill(status=502, content_type='text/html', body='Gateway error'))
                    page.locator('input[name=url]').fill('http://localhost/article')
                    page.locator('select[name=method]').select_option('4')
                    page.get_by_role('button', name='Fetch Page', exact=True).click()
                    page.wait_for_function("document.querySelector('#web-fetch-status').textContent.includes('HTTP 502')")
                    self.assertFalse(page.locator('#web-fetch-progress').is_visible())
                    self.assertTrue(page.get_by_role('button', name='Fetch Page', exact=True).is_enabled())
                    page.unroute('**/notes/api/web/fetch')
                    page.locator('input[name=url]').fill('http://localhost/article')
                    page.locator('select[name=method]').select_option('2')
                    page.get_by_role('button', name='Fetch Page', exact=True).click()
                    page.wait_for_url('**/notes/web/preview/**')
                    page.locator('#web-clip-title').fill('Browser title')
                    page.locator('#note-editor').fill('Edited browser article')
                    page.wait_for_timeout(1800)
                    self.assertEqual(shared.execute('SELECT COUNT(*) FROM lp_notes').fetchone()[0], 0)
                    page.get_by_role('button', name='Save', exact=True).click()
                    page.wait_for_url('**/notes/edit/*')
                    self.assertEqual(shared.execute('SELECT title FROM lp_notes').fetchone()[0], 'Browser title')
                    self.assertFalse(dialogs)
                    # A second preview can be edited and cancelled without an autosave.
                    page.goto(origin + '/notes/web', wait_until='domcontentloaded')
                    page.locator('input[name=url]').fill('http://localhost/article')
                    page.locator('select[name=method]').select_option('4')
                    page.get_by_role('button', name='Fetch Page', exact=True).click()
                    self.assertTrue(page.locator('#web-fetch-progress').is_visible())
                    self.assertIn('Fetching using Web Archive', page.locator('#web-fetch-status').inner_text())
                    self.assertFalse(page.locator('select[name=method]').is_enabled())
                    page.wait_for_function("/[1-9]\\d*s elapsed/.test(document.querySelector('#web-fetch-status').textContent)")
                    release_archive.set()
                    page.wait_for_url('**/notes/web/preview/**')
                    page.locator('#note-editor').fill('Discard this')
                    page.get_by_role('button', name='Cancel', exact=True).click()
                    page.wait_for_url(origin + '/notes/')
                    page.wait_for_timeout(200)
                    self.assertEqual(shared.execute('SELECT COUNT(*) FROM lp_notes').fetchone()[0], 1)
                    self.assertFalse(web._drafts)
                    self.assertEqual(requested_methods, [2, 4])
                    self.assertFalse(dialogs)
                    browser.close()
        finally:
            release_archive.set()
            server.shutdown()
            thread.join()
            server.server_close()

    def test_database_failure_rolls_back_files_note_place_and_link(self):
        draft = self.fetch()
        original = web._insert
        def fail_note(conn, table, values):
            if table == 'lp_notes':
                raise RuntimeError('simulated failure')
            return original(conn, table, values)
        with patch.object(web, '_insert', side_effect=fail_note):
            response = self.save(draft)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('simulated', response.get_json()['error'])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM lp_places').fetchone()[0], 0)
        self.assertEqual(list(self.target.iterdir()), [])
        self.assertIn(draft['token'], web._drafts)

    def test_session_isolation_and_save_cannot_be_replayed(self):
        draft = self.fetch()
        stranger = self.app.test_client()
        self.assertEqual(stranger.post('/notes/api/web/save/' + draft['token'], json={'title': 'stolen', 'content': 'x'}).status_code, 400)
        self.assertEqual(self.save(draft).status_code, 200)
        self.assertEqual(self.save(draft).status_code, 400)

    def test_image_downloads_and_failure_are_nonfatal(self):
        from PIL import Image
        buffer = BytesIO()
        Image.new('RGB', (100, 100)).save(buffer, format='PNG')
        value = result()
        value.images = ['https://example.com/pic.png', 'https://example.com/broken.png']
        content = '![photo](https://example.com/pic.png)\n![broken](https://example.com/broken.png)'
        with patch.object(clip, 'fetch_bytes', side_effect=[(buffer.getvalue(), value.images[0]), clip.WebClipError('failed')]):
            response = self.save(self.fetch(value), content=content)
        self.assertEqual(response.status_code, 200, response.data)
        payload = response.get_json()
        self.assertEqual(len(payload['warnings']), 1)
        path = self.target / payload['file_name']
        self.assertTrue((path.with_suffix('.assets') / 'image_001.png').exists())
        text = path.read_text(encoding='utf-8')
        self.assertIn('.assets/image_001.png', text)
        self.assertIn('https://example.com/broken.png', text)

    def test_image_adapter_failure_still_saves_note(self):
        value = result()
        value.images = ['https://example.com/image.png']
        draft = self.fetch(value)
        with patch.object(clip, 'download_images', side_effect=OSError('cannot create image')):
            response = self.save(draft)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['warnings'])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM lp_notes').fetchone()[0], 1)
