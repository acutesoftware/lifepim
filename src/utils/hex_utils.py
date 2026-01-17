#!/usr/bin/python3
# coding: utf-8
# hex_utils.py - hex dump helpers

def hex_dump(text, width=16):
    if text is None:
        text = ""
    data = text.encode("utf-8", errors="replace")
    rows = []
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        rows.append({"hex": hex_part, "ascii": ascii_part})
    if not rows:
        rows.append({"hex": "", "ascii": ""})
    return rows
