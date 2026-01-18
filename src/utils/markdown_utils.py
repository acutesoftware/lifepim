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


def _convert_obsidian_images(text, asset_resolver):
    if not asset_resolver:
        return text

    def _replace(match):
        asset_name = match.group(1).strip()
        if not asset_name:
            return match.group(0)
        return f"![]({asset_resolver(asset_name)})"

    return _OBSIDIAN_IMG_RE.sub(_replace, text)


def render_markdown(text, asset_resolver=None):
    if text is None:
        return ""
    text = _convert_obsidian_images(text, asset_resolver)
    if md_lib:
        return md_lib.markdown(text)
    escaped = html.escape(text)
    return escaped.replace("\n", "<br>")
