#!/usr/bin/python3
# coding: utf-8
# markdown_utils.py - basic markdown rendering helpers

import html

try:
    import markdown as md_lib
except Exception:
    md_lib = None


def render_markdown(text):
    if text is None:
        return ""
    if md_lib:
        return md_lib.markdown(text)
    escaped = html.escape(text)
    return escaped.replace("\n", "<br>")
