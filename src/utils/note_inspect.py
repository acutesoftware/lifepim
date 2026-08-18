import unicodedata


KIND_NORMAL = "normal"
KIND_UNICODE = "unicode"
KIND_SUSPICIOUS = "suspicious"
KIND_ERROR = "error"

_CONTROL_LABELS = {
    0x00: "NUL",
    0x01: "SOH",
    0x02: "STX",
    0x03: "ETX",
    0x04: "EOT",
    0x05: "ENQ",
    0x06: "ACK",
    0x07: "BEL",
    0x08: "BS",
    0x0B: "VT",
    0x0C: "FF",
    0x0E: "SO",
    0x0F: "SI",
    0x10: "DLE",
    0x11: "DC1",
    0x12: "DC2",
    0x13: "DC3",
    0x14: "DC4",
    0x15: "NAK",
    0x16: "SYN",
    0x17: "ETB",
    0x18: "CAN",
    0x19: "EM",
    0x1A: "SUB",
    0x1B: "ESC",
    0x1C: "FS",
    0x1D: "GS",
    0x1E: "RS",
    0x1F: "US",
    0x7F: "DEL",
}

_CONTROL_NAMES = {
    0x00: "NULL",
    0x01: "START OF HEADING",
    0x02: "START OF TEXT",
    0x03: "END OF TEXT",
    0x04: "END OF TRANSMISSION",
    0x05: "ENQUIRY",
    0x06: "ACKNOWLEDGE",
    0x07: "BELL",
    0x08: "BACKSPACE",
    0x0B: "LINE TABULATION",
    0x0C: "FORM FEED",
    0x0E: "SHIFT OUT",
    0x0F: "SHIFT IN",
    0x10: "DATA LINK ESCAPE",
    0x11: "DEVICE CONTROL ONE",
    0x12: "DEVICE CONTROL TWO",
    0x13: "DEVICE CONTROL THREE",
    0x14: "DEVICE CONTROL FOUR",
    0x15: "NEGATIVE ACKNOWLEDGE",
    0x16: "SYNCHRONOUS IDLE",
    0x17: "END OF TRANSMISSION BLOCK",
    0x18: "CANCEL",
    0x19: "END OF MEDIUM",
    0x1A: "SUBSTITUTE",
    0x1B: "ESCAPE",
    0x1C: "FILE SEPARATOR",
    0x1D: "GROUP SEPARATOR",
    0x1E: "RECORD SEPARATOR",
    0x1F: "UNIT SEPARATOR",
    0x7F: "DELETE",
}

_SPACE_LABELS = {
    0x00A0: "NBSP",
    0x2000: "EN QUAD",
    0x2001: "EM QUAD",
    0x2002: "EN SPACE",
    0x2003: "EM SPACE",
    0x2004: "THREE-PER-EM SPACE",
    0x2005: "FOUR-PER-EM SPACE",
    0x2006: "SIX-PER-EM SPACE",
    0x2007: "FIGURE SPACE",
    0x2008: "PUNCTUATION SPACE",
    0x2009: "THIN SPACE",
    0x200A: "HAIR SPACE",
    0x202F: "NARROW NBSP",
    0x205F: "MEDIUM MATHEMATICAL SPACE",
    0x3000: "IDEOGRAPHIC SPACE",
}

_ZERO_WIDTH_LABELS = {
    0x200B: "ZWSP",
    0x200C: "ZWNJ",
    0x200D: "ZWJ",
    0x2060: "WORD JOINER",
    0xFEFF: "BOM/ZWNBSP",
}

_BIDI_LABELS = {
    0x202A: "LRE",
    0x202B: "RLE",
    0x202C: "PDF",
    0x202D: "LRO",
    0x202E: "RLO",
    0x2066: "LRI",
    0x2067: "RLI",
    0x2068: "FSI",
    0x2069: "PDI",
}


def _code_point(ch):
    return f"U+{ord(ch):04X}"


def _byte_text(byte_values):
    return " ".join(f"{value:02X}" for value in byte_values)


def _utf8_text(ch):
    return _byte_text(ch.encode("utf-8"))


def _char_name(ch):
    code = ord(ch)
    if code in _CONTROL_NAMES:
        return _CONTROL_NAMES[code]
    if 0x80 <= code <= 0x9F:
        return f"C1 CONTROL {_code_point(ch)}"
    return unicodedata.name(ch, "UNKNOWN")


def _marker(label):
    return f"[{label}]"


def _token(kind, text, title="", line=None, column=None, byte_offset=None):
    return {
        "kind": kind,
        "text": text,
        "title": title,
        "line": line,
        "column": column,
        "byte_offset": byte_offset,
    }


def _details(ch, line, column, label=None):
    display = label or ch
    return "\n".join(
        [
            f"Character: {display}",
            f"Unicode: {_code_point(ch)}",
            f"Name: {_char_name(ch)}",
            f"UTF-8: {_utf8_text(ch)}",
            f"Line: {line}",
            f"Column: {column}",
        ]
    )


def classify_character(ch):
    code = ord(ch)
    if ch in "\t\r\n" or 0x20 <= code <= 0x7E:
        return {
            "kind": KIND_NORMAL,
            "text": ch,
            "label": "",
            "visible": False,
        }
    if code in _BIDI_LABELS:
        label = f"{_BIDI_LABELS[code]} {_code_point(ch)}"
        return {
            "kind": KIND_ERROR,
            "text": _marker(label),
            "label": label,
            "visible": True,
        }
    if code in _ZERO_WIDTH_LABELS:
        return {
            "kind": KIND_SUSPICIOUS,
            "text": _marker(_ZERO_WIDTH_LABELS[code]),
            "label": _ZERO_WIDTH_LABELS[code],
            "visible": True,
        }
    if code in _SPACE_LABELS:
        return {
            "kind": KIND_SUSPICIOUS,
            "text": _marker(_SPACE_LABELS[code]),
            "label": _SPACE_LABELS[code],
            "visible": True,
        }
    if code == 0xFFFD:
        return {
            "kind": KIND_ERROR,
            "text": _marker("REPLACEMENT U+FFFD"),
            "label": "REPLACEMENT CHARACTER",
            "visible": True,
        }
    if code in _CONTROL_LABELS or 0x80 <= code <= 0x9F:
        label = _CONTROL_LABELS.get(code) or _code_point(ch)
        return {
            "kind": KIND_ERROR,
            "text": _marker(label),
            "label": label,
            "visible": True,
        }
    return {
        "kind": KIND_UNICODE,
        "text": ch,
        "label": "",
        "visible": False,
    }


def _advance_position(ch, line, column, previous_cr=False):
    if ch == "\r":
        return line + 1, 1, True
    if ch == "\n":
        if previous_cr:
            return line, 1, False
        return line + 1, 1, False
    return line, column + 1, False


def _flush_normal(tokens, parts):
    if parts:
        tokens.append(_token(KIND_NORMAL, "".join(parts)))
        parts.clear()


def _summary():
    return {
        "ascii": 0,
        "non_ascii": 0,
        "suspicious": 0,
        "errors": 0,
    }


def inspect_note_bytes(data):
    data = data or b""
    decoded = data.decode("utf-8", "surrogateescape")
    tokens = []
    normal_parts = []
    counts = _summary()
    line = 1
    column = 1
    byte_offset = 0
    previous_cr = False
    index = 0

    while index < len(decoded):
        ch = decoded[index]
        code = ord(ch)
        if 0xDC80 <= code <= 0xDCFF:
            _flush_normal(tokens, normal_parts)
            start_line = line
            start_column = column
            start_offset = byte_offset
            invalid_bytes = []
            while index < len(decoded):
                next_code = ord(decoded[index])
                if not 0xDC80 <= next_code <= 0xDCFF:
                    break
                invalid_bytes.append(next_code - 0xDC00)
                index += 1
                byte_offset += 1
                column += 1
                previous_cr = False
            byte_label = _byte_text(invalid_bytes)
            tokens.append(
                _token(
                    KIND_ERROR,
                    _marker(f"INVALID UTF-8: {byte_label}"),
                    "\n".join(
                        [
                            "Type: Invalid UTF-8",
                            f"Bytes: {byte_label}",
                            f"Line: {start_line}",
                            f"Column: {start_column}",
                            f"Byte offset: {start_offset}",
                        ]
                    ),
                    line=start_line,
                    column=start_column,
                    byte_offset=start_offset,
                )
            )
            counts["errors"] += 1
            continue

        classification = classify_character(ch)
        kind = classification["kind"]
        char_byte_len = len(ch.encode("utf-8"))
        if kind == KIND_NORMAL:
            normal_parts.append(ch)
            counts["ascii"] += 1
        else:
            _flush_normal(tokens, normal_parts)
            label = classification.get("label") or None
            tokens.append(
                _token(
                    kind,
                    classification["text"],
                    _details(ch, line, column, label=label),
                    line=line,
                    column=column,
                    byte_offset=byte_offset,
                )
            )
            if kind == KIND_UNICODE:
                counts["non_ascii"] += 1
            elif kind == KIND_SUSPICIOUS:
                counts["suspicious"] += 1
            else:
                counts["errors"] += 1

        line, column, previous_cr = _advance_position(ch, line, column, previous_cr)
        byte_offset += char_byte_len
        index += 1

    _flush_normal(tokens, normal_parts)
    return {
        "tokens": tokens,
        "summary": counts,
    }
