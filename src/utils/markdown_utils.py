#!/usr/bin/python3
# coding: utf-8
# markdown_utils.py - basic markdown rendering helpers

import html
import inspect
import re

try:
    import markdown as md_lib
except Exception:
    md_lib = None


_OBSIDIAN_IMG_RE = re.compile(r"!\[\[([^\]]+)\]\]")
_OBSIDIAN_WIKI_LINK_RE = re.compile(r"(?<!!)\[\[([^\]\n]+)\]\]")
_LIFEPIM_IMG_RE = re.compile(r"\[img\](.*?)\[/img\]", re.IGNORECASE | re.DOTALL)
_MARKDOWN_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
_HTML_IMG_RE = re.compile(r"(?is)<img\b([^>]*?)\bsrc\s*=\s*(['\"]?)([^'\"\s>]+)\2([^>]*)>")
_FENCE_RE = re.compile(r"^```[\w+-]*\s*$")
_FENCE_CLOSE_RE = re.compile(r"^```\s*$")


def _is_absolute_asset(source):
    source = (source or "").strip().lower()
    return (
        source.startswith("http://")
        or source.startswith("https://")
        or source.startswith("data:")
        or source.startswith("/")
        or source.startswith("#")
    )


def _is_absolute_link_target(source):
    source = (source or "").strip().lower()
    return (
        _is_absolute_asset(source)
        or source.startswith("mailto:")
        or source.startswith("tel:")
        or source.startswith("ftp://")
    )


def _resolve_asset(source, asset_resolver):
    source = html.unescape((source or "").strip())
    if not source:
        return ""
    if _is_absolute_asset(source):
        return source
    return asset_resolver(source) if asset_resolver else source


def _image_html(source, alt, asset_resolver):
    resolved = _resolve_asset(source, asset_resolver)
    if not resolved:
        return ""
    return '<img src="{0}" alt="{1}">'.format(
        html.escape(resolved, quote=True),
        html.escape((alt or "").strip(), quote=True),
    )


def _markdown_image_target(value):
    target = (value or "").strip()
    if target.startswith("<") and target.endswith(">"):
        return target[1:-1].strip()
    title = target.find(' "')
    if title >= 0:
        target = target[:title].strip()
    return target


def _convert_html_images(text, asset_resolver):
    if not asset_resolver:
        return text

    def _replace(match):
        source = match.group(3).strip()
        if not source or _is_absolute_asset(source):
            return match.group(0)
        resolved = _resolve_asset(source, asset_resolver)
        return '<img{0}src="{1}"{2}>'.format(
            match.group(1),
            html.escape(resolved, quote=True),
            match.group(4),
        )

    return _HTML_IMG_RE.sub(_replace, text)


def _convert_obsidian_images(text, asset_resolver):
    if not asset_resolver:
        return text

    def _replace(match):
        asset_name = match.group(1).strip()
        if not asset_name:
            return match.group(0)
        return _image_html(asset_name, asset_name, asset_resolver)

    return _OBSIDIAN_IMG_RE.sub(_replace, text)


def _convert_lifepim_images(text, asset_resolver):
    if not asset_resolver:
        return text

    def _replace(match):
        asset_name = match.group(1).strip()
        if not asset_name:
            return match.group(0)
        return _image_html(asset_name, asset_name, asset_resolver)

    return _LIFEPIM_IMG_RE.sub(_replace, text)


def _convert_markdown_images(text, asset_resolver):
    if not asset_resolver:
        return text

    def _replace(match):
        source = _markdown_image_target(match.group(2))
        if not source or _is_absolute_asset(source):
            return match.group(0)
        return _image_html(source, match.group(1), asset_resolver)

    return _MARKDOWN_IMG_RE.sub(_replace, text)


def _convert_note_images(text, asset_resolver):
    text = _convert_html_images(text, asset_resolver)
    text = _convert_obsidian_images(text, asset_resolver)
    text = _convert_lifepim_images(text, asset_resolver)
    return _convert_markdown_images(text, asset_resolver)


def _wiki_link_label_html(title):
    return html.escape(title, quote=False).replace("*", "&#42;")


def _wiki_link_html(title, resolved):
    label = _wiki_link_label_html(title)
    status = (resolved or {}).get("status") or "broken"
    if status == "resolved" and resolved.get("url"):
        link_title = (resolved.get("title") or title).strip()
        return '<a class="wiki-link wiki-link-resolved" href="{0}" title="{1}">{2}</a>'.format(
            html.escape(resolved["url"], quote=True),
            html.escape(link_title, quote=True),
            label,
        )
    if status == "ambiguous":
        count = resolved.get("count") or len(resolved.get("matches") or [])
        title_attr = f"Ambiguous link: {count} notes match" if count else "Ambiguous link"
        return '<span class="wiki-link wiki-link-ambiguous" title="{0}">{1}</span>'.format(
            html.escape(title_attr, quote=True),
            label,
        )
    return '<span class="wiki-link wiki-link-broken" title="{0}">{1}</span>'.format(
        html.escape("Broken link: no matching note", quote=True),
        label,
    )


def _obsidian_wiki_link_parts(value):
    parts = [part.strip() for part in (value or "").split("|")]
    title = parts[0] if parts else ""
    target_note_id = ""
    label = ""
    for part in parts[1:]:
        match = re.match(r"(?i)^note:(\d+)$", part)
        if match:
            target_note_id = match.group(1)
            break
        if not label:
            label = part
    if not title:
        for part in parts:
            if not re.match(r"(?i)^note:\d+$", part or ""):
                title = part
                break
    return title, target_note_id, label or title


def _resolve_wiki_link(wiki_link_resolver, title, target_note_id):
    try:
        params = inspect.signature(wiki_link_resolver).parameters
        if len(params) >= 2:
            return wiki_link_resolver(title, target_note_id=target_note_id)
    except (TypeError, ValueError):
        pass
    try:
        return wiki_link_resolver(title)
    except Exception:
        return {"status": "broken"}


def _convert_obsidian_wiki_links(text, wiki_link_resolver):
    if not wiki_link_resolver:
        return text

    def _replace(match):
        title, target_note_id, label = _obsidian_wiki_link_parts(match.group(1))
        if not title:
            return match.group(0)
        resolved = _resolve_wiki_link(wiki_link_resolver, title, target_note_id)
        return _wiki_link_html(label, resolved)

    return _OBSIDIAN_WIKI_LINK_RE.sub(_replace, text)


def _markdown_link_target(value):
    return _markdown_image_target(value)


def _is_markdown_note_link_target(target):
    path = (target or "").split("#", 1)[0].split("?", 1)[0].strip().lower()
    return path.endswith(".md")


def _note_link_html(label, resolved):
    text = _wiki_link_label_html(label)
    status = (resolved or {}).get("status") or "broken"
    if status == "resolved" and resolved.get("url"):
        link_title = (resolved.get("title") or label).strip()
        return '<a class="note-link note-link-resolved" href="{0}" title="{1}">{2}</a>'.format(
            html.escape(resolved["url"], quote=True),
            html.escape(link_title, quote=True),
            text,
        )
    if status == "broken":
        return '<span class="note-link note-link-broken" title="{0}">{1}</span>'.format(
            html.escape("Broken link: no matching note", quote=True),
            text,
        )
    if status == "ambiguous":
        count = (resolved or {}).get("count") or len((resolved or {}).get("matches") or [])
        title_attr = f"Ambiguous link: {count} notes match" if count else "Ambiguous link"
        return '<span class="note-link note-link-ambiguous" title="{0}">{1}</span>'.format(
            html.escape(title_attr, quote=True),
            text,
        )
    return ""


def _convert_markdown_note_links(text, link_resolver):
    if not link_resolver:
        return text

    def _replace(match):
        label = match.group(1)
        target = _markdown_link_target(match.group(2))
        if not target or _is_absolute_link_target(target):
            return match.group(0)
        if not _is_markdown_note_link_target(target):
            return match.group(0)
        resolved = link_resolver(target)
        if not resolved:
            return match.group(0)
        replacement = _note_link_html(label, resolved)
        return replacement or match.group(0)

    return _MARKDOWN_LINK_RE.sub(_replace, text)


def _escape_fallback_paragraph(value):
    placeholders = []

    def _replace_html(match):
        token = f"@@LIFEPIM_HTML_{len(placeholders)}@@"
        placeholders.append((token, match.group(0)))
        return token

    value = _HTML_IMG_RE.sub(_replace_html, value)
    value = re.sub(r"<a\b[^>]*\bclass=\"wiki-link\b[^>]*>.*?</a>", _replace_html, value)
    value = re.sub(r"<a\b[^>]*\bclass=\"note-link\b[^>]*>.*?</a>", _replace_html, value)
    value = re.sub(r"<span\b[^>]*\bclass=\"wiki-link\b[^>]*>.*?</span>", _replace_html, value)
    value = re.sub(r"<span\b[^>]*\bclass=\"note-link\b[^>]*>.*?</span>", _replace_html, value)
    escaped = html.escape(value).replace("\n", "<br>")
    for token, html_fragment in placeholders:
        escaped = escaped.replace(token, html_fragment)
    return escaped


def _render_fallback_markdown(text):
    blocks = []
    paragraph_lines = []
    code_lines = []
    in_code = False

    def flush_paragraph():
        if paragraph_lines:
            blocks.append(_escape_fallback_paragraph("\n".join(paragraph_lines)))
            paragraph_lines.clear()

    def flush_code():
        blocks.append("<pre><code>{0}</code></pre>".format(html.escape("\n".join(code_lines))))
        code_lines.clear()

    for line in text.splitlines():
        if in_code:
            if _FENCE_CLOSE_RE.match(line.strip()):
                flush_code()
                in_code = False
            else:
                code_lines.append(line)
            continue
        if _FENCE_RE.match(line.strip()):
            flush_paragraph()
            in_code = True
            continue
        paragraph_lines.append(line)

    if in_code:
        paragraph_lines.insert(0, "```")
        paragraph_lines.extend(code_lines)
    flush_paragraph()
    return "<br>".join(blocks)


def render_markdown(text, asset_resolver=None, allow_html=True, wiki_link_resolver=None, link_resolver=None):
    if text is None:
        return ""
    if not allow_html:
        text = html.escape(text, quote=False)
    text = _convert_note_images(text, asset_resolver)
    text = _convert_obsidian_wiki_links(text, wiki_link_resolver)
    text = _convert_markdown_note_links(text, link_resolver)
    if md_lib:
        return md_lib.markdown(text, extensions=["fenced_code", "nl2br", "sane_lists", "tables"])
    return _render_fallback_markdown(text)
