from dataclasses import asdict, dataclass, field
import re


KNOWN_METADATA = {
    "key",
    "title",
    "project_id",
    "project",
    "status",
    "tags",
    "estimated_minutes",
    "difficulty",
    "last_verified",
}

SECTION_ALIASES = {
    "summary": "summary",
    "outcome": "outcome",
    "parts": "parts",
    "ingredients": "parts",
    "materials": "parts",
    "inputs": "parts",
    "things needed": "parts",
    "requirements": "parts",
    "tools": "tools",
    "tools needed": "tools",
    "equipment": "tools",
    "software": "tools",
    "steps": "steps",
    "method": "steps",
    "procedure": "steps",
    "instructions": "steps",
    "check": "check",
    "checks": "check",
    "validation": "check",
    "success criteria": "check",
    "notes": "notes",
}

REF_RE = re.compile(r"^\[\[(?P<kind>part|tool|step|howto):(?P<key>[^|\]]+)(?:\|(?P<label>[^\]]+))?\]\]$")
STEP_RE = re.compile(r"^\s*(?P<num>\d+)\.\s+(?P<body>.*)$")
META_RE = re.compile(r"^\s*(?P<name>Title|Expected|Warning|Optional|Image|Step|Howto|Mode|Notes):\s*(?P<value>.*)$", re.I)


@dataclass
class Diagnostic:
    severity: str
    message: str
    source_line: int | None = None
    code: str = ""


@dataclass
class ParsedPart:
    name: str
    quantity: float | None = None
    unit: str = ""
    optional: bool = False
    notes: str = ""
    part_key: str = ""
    source_line: int | None = None
    resolution: str = "unresolved"
    matched_id: int | None = None


@dataclass
class ParsedTool:
    name: str
    optional: bool = False
    notes: str = ""
    tool_key: str = ""
    source_line: int | None = None
    resolution: str = "unresolved"
    matched_id: int | None = None


@dataclass
class ParsedStep:
    order: int
    instruction: str
    step_title: str = ""
    expected_result: str = ""
    warning: str = ""
    optional: bool = False
    image_filepath: str = ""
    notes: str = ""
    step_key: str = ""
    step_type: str = "instruction"
    child_howto_ref: str = ""
    child_mode: str = "linked"
    source_line: int | None = None
    resolution: str = "unresolved"
    matched_id: int | None = None
    child_howto_id: int | None = None
    child_resolution: str = ""


@dataclass
class ParsedHowto:
    metadata: dict = field(default_factory=dict)
    title: str = ""
    summary: str = ""
    outcome: str = ""
    check_content: str = ""
    notes_content: str = ""
    parts: list[ParsedPart] = field(default_factory=list)
    tools: list[ParsedTool] = field(default_factory=list)
    steps: list[ParsedStep] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    markdown_full_content: str = ""

    def to_dict(self):
        return asdict(self)


def slug_key(value):
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "untitled"


def normalize_name(value):
    return " ".join((value or "").strip().lower().split())


def _coerce_scalar(value):
    value = (value or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def parse_frontmatter(markdown):
    lines = markdown.splitlines()
    diagnostics = []
    metadata = {}
    body_start = 0
    if not lines or lines[0].strip() != "---":
        return metadata, markdown, diagnostics
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        diagnostics.append(Diagnostic("ERROR", "YAML front matter is not closed.", 1, "YAML_UNCLOSED"))
        return metadata, markdown, diagnostics

    current_key = None
    for idx, raw in enumerate(lines[1:end_idx], start=2):
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith("-"):
            if not current_key:
                diagnostics.append(Diagnostic("ERROR", "YAML list item has no field.", idx, "YAML_LIST"))
                continue
            metadata.setdefault(current_key, [])
            if not isinstance(metadata[current_key], list):
                diagnostics.append(Diagnostic("ERROR", f"YAML field '{current_key}' mixes scalar and list values.", idx, "YAML_MIXED"))
                continue
            metadata[current_key].append(_coerce_scalar(line.lstrip()[1:].strip()))
            continue
        if ":" not in line:
            diagnostics.append(Diagnostic("ERROR", "YAML line is malformed.", idx, "YAML_MALFORMED"))
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if not key:
            diagnostics.append(Diagnostic("ERROR", "YAML field name is empty.", idx, "YAML_KEY"))
            continue
        current_key = key
        value = value.strip()
        metadata[key] = [] if value == "" else _coerce_scalar(value)
        if key not in KNOWN_METADATA:
            diagnostics.append(Diagnostic("WARNING", f"Unknown YAML field '{key}'.", idx, "YAML_UNKNOWN"))
    body_start = end_idx + 1
    return metadata, "\n".join(lines[body_start:]), diagnostics


def parse_sections(body):
    sections = {}
    unknown = []
    current = None
    current_heading = ""
    for idx, line in enumerate(body.splitlines(), start=1):
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            raw_heading = match.group(1).strip()
            canonical = SECTION_ALIASES.get(raw_heading.lower())
            current = canonical
            current_heading = raw_heading
            if canonical:
                sections.setdefault(canonical, [])
            else:
                unknown.append((idx, raw_heading))
            continue
        if current:
            sections[current].append((idx, line))
        elif current_heading:
            unknown.append((idx, current_heading))
    return sections, unknown


def _extract_ref(value):
    value = (value or "").strip()
    match = REF_RE.match(value)
    if not match:
        return "", "", value
    return match.group("kind"), match.group("key").strip(), (match.group("label") or match.group("key")).strip()


def _parse_optional_notes(parts):
    optional = False
    notes = ""
    for value in parts:
        text = value.strip()
        if text.lower() == "optional":
            optional = True
        elif text:
            notes = text if not notes else f"{notes} | {text}"
    return optional, notes


def parse_parts(section_lines):
    parts = []
    for line_no, line in section_lines:
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        cols = [col.strip() for col in stripped[1:].split("|")]
        ref_kind, ref_key, label = _extract_ref(cols[0])
        qty = None
        if len(cols) > 1 and cols[1]:
            try:
                qty = float(cols[1])
            except ValueError:
                pass
        optional, notes = _parse_optional_notes(cols[3:])
        parts.append(
            ParsedPart(
                name=label,
                quantity=qty,
                unit=cols[2] if len(cols) > 2 else "",
                optional=optional,
                notes=notes,
                part_key=ref_key if ref_kind == "part" else "",
                source_line=line_no,
            )
        )
    return parts


def parse_tools(section_lines):
    tools = []
    for line_no, line in section_lines:
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        cols = [col.strip() for col in stripped[1:].split("|")]
        ref_kind, ref_key, label = _extract_ref(cols[0])
        optional, notes = _parse_optional_notes(cols[1:])
        tools.append(
            ParsedTool(
                name=label,
                optional=optional,
                notes=notes,
                tool_key=ref_key if ref_kind == "tool" else "",
                source_line=line_no,
            )
        )
    return tools


def _finish_step(steps, step):
    if not step:
        return
    step.instruction = " ".join(step.instruction.split()).strip()
    steps.append(step)


def parse_steps(section_lines):
    steps = []
    current = None
    for line_no, line in section_lines:
        step_match = STEP_RE.match(line)
        if step_match:
            _finish_step(steps, current)
            body = step_match.group("body").strip()
            ref_kind, ref_key, label = _extract_ref(body)
            order = int(step_match.group("num"))
            current = ParsedStep(order=order, instruction=label, source_line=line_no)
            if ref_kind == "step":
                current.step_key = ref_key
            elif ref_kind == "howto":
                current.step_type = "howto"
                current.child_howto_ref = ref_key
                current.child_mode = "linked"
            continue
        if current is None:
            continue
        meta = META_RE.match(line)
        if meta:
            name = meta.group("name").lower()
            value = meta.group("value").strip()
            if name == "title":
                current.step_title = value
            elif name == "expected":
                current.expected_result = value
            elif name == "warning":
                current.warning = value
            elif name == "optional":
                current.optional = value.lower() in {"1", "true", "yes", "y"}
            elif name == "image":
                current.image_filepath = value
            elif name == "step":
                current.step_key = value
            elif name == "howto":
                current.step_type = "howto"
                current.child_howto_ref = value
            elif name == "mode":
                current.child_mode = value or "linked"
            elif name == "notes":
                current.notes = value
        elif line.strip():
            current.instruction = f"{current.instruction} {line.strip()}"
    _finish_step(steps, current)
    return steps


def parse_markdown(markdown, default_title=""):
    parsed = ParsedHowto(markdown_full_content=markdown or "")
    metadata, body, diagnostics = parse_frontmatter(markdown or "")
    parsed.metadata = metadata
    parsed.diagnostics.extend(diagnostics)
    sections, unknown = parse_sections(body)
    for line_no, heading in unknown:
        parsed.diagnostics.append(Diagnostic("WARNING", f"Unknown Markdown section '{heading}'.", line_no, "SECTION_UNKNOWN"))
    parsed.title = str(metadata.get("title") or "").strip()
    if not parsed.title:
        h1 = re.search(r"^#\s+(.+?)\s*$", body, flags=re.M)
        if h1:
            parsed.title = h1.group(1).strip()
    if not parsed.title and default_title:
        parsed.title = default_title.strip()
    if not parsed.title:
        parsed.diagnostics.append(Diagnostic("ERROR", "A title is required in YAML or an H1 heading.", None, "TITLE_REQUIRED"))
    if "key" not in metadata and parsed.title:
        parsed.metadata["key"] = slug_key(parsed.title)
        if not default_title:
            parsed.diagnostics.append(Diagnostic("WARNING", f"Suggested key '{parsed.metadata['key']}' generated from title.", None, "KEY_SUGGESTED"))
    parsed.summary = _section_text(sections.get("summary", []))
    parsed.outcome = _section_text(sections.get("outcome", []))
    if not parsed.outcome:
        parsed.diagnostics.append(Diagnostic("WARNING", "Outcome is recommended.", None, "OUTCOME_RECOMMENDED"))
    parsed.check_content = _section_text(sections.get("check", []))
    parsed.notes_content = _section_text(sections.get("notes", []))
    parsed.parts = parse_parts(sections.get("parts", []))
    parsed.tools = parse_tools(sections.get("tools", []))
    parsed.steps = parse_steps(sections.get("steps", []))
    return parsed


def _section_text(lines):
    return "\n".join(line for _, line in lines).strip()
