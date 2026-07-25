#!/usr/bin/python3
# coding: utf-8
# markdown_utils.py - basic markdown rendering helpers

import html
import re

try:
    import markdown as md_lib
except Exception:
    md_lib = None


_OBSIDIAN_IMG_RE = re.compile(r"!\[\[([^\]]+)\]\]")
_LIFEPIM_IMG_RE = re.compile(r"\[img\](.*?)\[/img\]", re.IGNORECASE | re.DOTALL)
_MARKDOWN_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
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


def _escape_fallback_paragraph(value):
    placeholders = []

    def _replace_img(match):
        token = f"@@LIFEPIM_IMG_{len(placeholders)}@@"
        placeholders.append((token, match.group(0)))
        return token

    value = _HTML_IMG_RE.sub(_replace_img, value)
    escaped = html.escape(value).replace("\n", "<br>")
    for token, image_tag in placeholders:
        escaped = escaped.replace(token, image_tag)
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


def render_markdown(text, asset_resolver=None, allow_html=True):
    if text is None:
        return ""
    if not allow_html:
        text = html.escape(text, quote=False)
    text = _convert_note_images(text, asset_resolver)
    if md_lib:
        return md_lib.markdown(text, extensions=["fenced_code", "nl2br", "sane_lists", "tables"])
    return _render_fallback_markdown(text)
