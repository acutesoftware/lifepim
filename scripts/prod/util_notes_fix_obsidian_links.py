#!/usr/bin/env python3
# coding: utf-8

"""Safely convert Obsidian wiki links to explicit relative markdown paths."""

from __future__ import annotations

import csv
import logging
import os
import posixpath
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


ROOT_FOLDER = r"N:\duncan\LifePIM_Data\DATA\notes"

DRY_RUN = False

BACKUP_FILES = False

VERBOSE = True

CASE_SENSITIVE = False

RECURSIVE = True

# Use 0 when ROOT_FOLDER is the Obsidian vault root.
# Increase this only when scanning a subfolder and links need to resolve to sibling folders above it.
LOOKUP_PARENT_LEVELS = 0

SCRIPT_FOLDER = Path(__file__).resolve().parent
LOG_FILE = "util_notes_fix_obsidian_links.log"
CSV_REPORT_FILE = "util_notes_fix_obsidian_links.csv"


WIKI_LINK_RE = re.compile(r"(?<!!)\[\[([^\[\]\r\n]+?)\]\]")


@dataclass(frozen=True)
class NoteFile:
    abs_path: Path
    rel_path: str
    stem: str
    folder: str


@dataclass
class NoteIndex:
    root: Path
    key_roots: list[Path] = field(default_factory=list)
    by_stem: dict[str, list[NoteFile]] = field(default_factory=dict)
    by_rel_path: dict[str, list[NoteFile]] = field(default_factory=dict)


@dataclass
class LinkResult:
    source_file: str
    line: int
    original_link: str
    resolved_path: str
    status: str
    replacement_link: str = ""
    candidates: list[str] = field(default_factory=list)


@dataclass
class Summary:
    files_scanned: int = 0
    wiki_links_found: int = 0
    already_explicit: int = 0
    converted: int = 0
    ambiguous: int = 0
    missing: int = 0
    files_modified: int = 0
    failures: list[str] = field(default_factory=list)


def main() -> None:
    run()


def run(
    root_folder: str | os.PathLike[str] = ROOT_FOLDER,
    dry_run: bool = DRY_RUN,
    backup_files: bool = BACKUP_FILES,
    verbose: bool = VERBOSE,
    case_sensitive: bool = CASE_SENSITIVE,
    recursive: bool = RECURSIVE,
    lookup_parent_levels: int = LOOKUP_PARENT_LEVELS,
    log_file: str | os.PathLike[str] = LOG_FILE,
    csv_report_file: str | os.PathLike[str] = CSV_REPORT_FILE,
) -> Summary:
    root = Path(root_folder).resolve()
    log_path = resolve_output_path(log_file, root)
    csv_report_path = resolve_output_path(csv_report_file, root)
    summary = Summary()
    logger = configure_logger(log_path)

    logger.info("Starting Obsidian link fix")
    logger.info("Root folder: %s", root)
    logger.info("Log file: %s", log_path)
    logger.info("CSV report file: %s", csv_report_path)
    logger.info("Dry run: %s", dry_run)

    if not root.exists() or not root.is_dir():
        message = f"Root folder does not exist or is not a directory: {root}"
        summary.failures.append(message)
        logger.error(message)
        print(message)
        write_csv_report(csv_report_path, [])
        print_summary(summary)
        close_logger(logger)
        return summary

    try:
        lookup_root, key_roots = get_lookup_roots(root, lookup_parent_levels)
        index, scan_failures = build_index(
            root=lookup_root,
            recursive=recursive,
            case_sensitive=case_sensitive,
            display_root=root,
            key_roots=key_roots,
        )
        process_notes, process_failures = collect_note_files(
            root=root,
            recursive=recursive,
            display_root=root,
        )
        summary.files_scanned = len(process_notes)
        summary.failures.extend(scan_failures)
        summary.failures.extend(process_failures)
        logger.info("Lookup root: %s", lookup_root)
        logger.info("Lookup parent levels: %s", lookup_parent_levels)
        logger.info("Lookup files indexed: %s", len({note.abs_path for notes in index.by_rel_path.values() for note in notes}))

        records: list[LinkResult] = []
        for note in sorted(process_notes, key=lambda item: item.rel_path.lower()):
            try:
                file_records, modified = process_file(
                    note=note,
                    index=index,
                    dry_run=dry_run,
                    backup_files=backup_files,
                    verbose=verbose,
                    logger=logger,
                    case_sensitive=case_sensitive,
                )
            except Exception as exc:
                message = f"{note.rel_path}: {exc}"
                summary.failures.append(message)
                logger.exception("Failed processing %s", note.rel_path)
                continue

            records.extend(file_records)
            for record in file_records:
                summary.wiki_links_found += 1
                if record.status == "already_explicit":
                    summary.already_explicit += 1
                elif record.status == "converted":
                    summary.converted += 1
                elif record.status == "ambiguous":
                    summary.ambiguous += 1
                elif record.status == "missing":
                    summary.missing += 1

            if modified:
                summary.files_modified += 1

        write_csv_report(csv_report_path, records)
        print_summary(summary)
        if summary.failures:
            print_failures(summary.failures)
        logger.info("Finished Obsidian link fix")
        return summary
    finally:
        close_logger(logger)


def configure_logger(log_file: str | os.PathLike[str]) -> logging.Logger:
    logger = logging.getLogger("util_notes_fix_obsidian_links")
    logger.setLevel(logging.INFO)
    close_logger(logger)

    handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def resolve_output_path(output_file: str | os.PathLike[str], root: Path) -> Path:
    path = Path(output_file)
    if path.is_absolute():
        return path
    return root / path


def close_logger(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)


def build_index(
    root: Path,
    recursive: bool,
    case_sensitive: bool,
    display_root: Path | None = None,
    key_roots: list[Path] | None = None,
) -> tuple[NoteIndex, list[str]]:
    display_root = display_root or root
    key_roots = key_roots or [root]
    index = NoteIndex(root=root, key_roots=key_roots)
    notes, failures = collect_note_files(root, recursive, display_root)

    for note in notes:
        try:
            for rel_path in relative_keys_for_roots(note.abs_path, key_roots):
                add_unique_note(index.by_rel_path, normalize_key(rel_path, case_sensitive), note)
            index.by_stem.setdefault(normalize_key(note.stem, case_sensitive), []).append(note)
        except Exception as exc:
            failures.append(f"{note.abs_path}: {exc}")

    return index, failures


def collect_note_files(
    root: Path,
    recursive: bool,
    display_root: Path,
) -> tuple[list[NoteFile], list[str]]:
    notes: list[NoteFile] = []
    failures: list[str] = []

    for path in iter_markdown_files(root, recursive, failures):
        try:
            resolved = path.resolve()
            rel_path = display_rel_path(resolved, display_root, root)
            notes.append(
                NoteFile(
                    abs_path=resolved,
                    rel_path=rel_path,
                    stem=path.stem,
                    folder=to_posix(Path(rel_path).parent),
                )
            )
        except Exception as exc:
            failures.append(f"{path}: {exc}")

    return notes, failures


def add_unique_note(index: dict[str, list[NoteFile]], key: str, note: NoteFile) -> None:
    notes = index.setdefault(key, [])
    if note.abs_path not in {item.abs_path for item in notes}:
        notes.append(note)


def get_lookup_roots(root: Path, lookup_parent_levels: int) -> tuple[Path, list[Path]]:
    key_roots = [root]
    current = root
    for _level in range(max(0, lookup_parent_levels)):
        parent = current.parent
        if parent == current:
            break
        current = parent
        key_roots.append(current)
    return current, key_roots


def relative_keys_for_roots(path: Path, roots: list[Path]) -> list[str]:
    keys: list[str] = []
    for root in roots:
        try:
            keys.append(to_posix(path.relative_to(root)))
        except ValueError:
            continue
    return keys


def display_rel_path(path: Path, display_root: Path, fallback_root: Path) -> str:
    try:
        return to_posix(path.relative_to(display_root))
    except ValueError:
        return to_posix(path.relative_to(fallback_root))


def iter_markdown_files(root: Path, recursive: bool, failures: list[str]) -> Iterable[Path]:
    if recursive:
        for dirpath, _dirnames, filenames in os.walk(root, onerror=lambda exc: failures.append(str(exc))):
            for filename in filenames:
                if filename.lower().endswith(".md"):
                    yield Path(dirpath) / filename
    else:
        try:
            for item in root.iterdir():
                if item.is_file() and item.name.lower().endswith(".md"):
                    yield item
        except Exception as exc:
            failures.append(f"{root}: {exc}")


def process_file(
    note: NoteFile,
    index: NoteIndex,
    dry_run: bool,
    backup_files: bool,
    verbose: bool,
    logger: logging.Logger,
    case_sensitive: bool,
) -> tuple[list[LinkResult], bool]:
    text = read_text(note.abs_path)
    replacements: list[tuple[int, int, str]] = []
    records: list[LinkResult] = []

    for match in WIKI_LINK_RE.finditer(text):
        original_link = match.group(0)
        line = text.count("\n", 0, match.start()) + 1
        record = resolve_wiki_link(
            note=note,
            index=index,
            raw_link_body=match.group(1),
            original_link=original_link,
            line=line,
            case_sensitive=case_sensitive,
        )
        records.append(record)
        log_record(logger, record)

        if record.status == "converted":
            replacements.append((match.start(), match.end(), record.replacement_link))
            if dry_run and verbose:
                print_dry_run_change(record)
        elif record.status == "ambiguous" and verbose:
            print_ambiguous(record)
        elif record.status == "missing" and verbose:
            print_missing(record)

    if not replacements:
        return records, False

    new_text = apply_replacements(text, replacements)
    if dry_run:
        return records, False

    stat = note.abs_path.stat()
    if backup_files:
        backup_path = note.abs_path.with_name(note.abs_path.name + ".bak")
        shutil.copy2(note.abs_path, backup_path)
        logger.info("BACKUP %s -> %s", note.rel_path, backup_path)

    write_text(note.abs_path, new_text)
    os.utime(note.abs_path, (stat.st_atime, stat.st_mtime))
    logger.info("MODIFIED %s", note.rel_path)
    return records, True


def resolve_wiki_link(
    note: NoteFile,
    index: NoteIndex,
    raw_link_body: str,
    original_link: str,
    line: int,
    case_sensitive: bool,
) -> LinkResult:
    target, alias = split_target_alias(raw_link_body)
    target = target.strip()
    source_file = note.rel_path

    if not target:
        return LinkResult(source_file, line, original_link, "", "missing")

    if has_markdown_extension(target):
        resolved = resolve_path_target(note, index, target, case_sensitive)
        if len(resolved) == 1:
            rel_target = relative_link_target(note, resolved[0])
            return LinkResult(source_file, line, original_link, rel_target, "already_explicit")
        if len(resolved) > 1:
            candidates = sorted({item.rel_path for item in resolved}, key=str.lower)
            return LinkResult(source_file, line, original_link, ";".join(candidates), "ambiguous", candidates=candidates)
        return LinkResult(source_file, line, original_link, "", "missing")

    if contains_folder(target):
        resolved = resolve_path_target(note, index, target + ".md", case_sensitive)
        if len(resolved) == 1:
            rel_target = relative_link_target(note, resolved[0])
            return converted_result(source_file, line, original_link, rel_target, alias)
        if len(resolved) > 1:
            candidates = sorted({item.rel_path for item in resolved}, key=str.lower)
            return LinkResult(source_file, line, original_link, ";".join(candidates), "ambiguous", candidates=candidates)
        return LinkResult(source_file, line, original_link, "", "missing")

    local_matches = resolve_path_target(note, index, target + ".md", case_sensitive)
    if len(local_matches) == 1:
        rel_target = relative_link_target(note, local_matches[0])
        return converted_result(source_file, line, original_link, rel_target, alias)
    if len(local_matches) > 1:
        candidates = sorted({item.rel_path for item in local_matches}, key=str.lower)
        return LinkResult(source_file, line, original_link, ";".join(candidates), "ambiguous", candidates=candidates)

    matches = index.by_stem.get(normalize_key(target, case_sensitive), [])
    if len(matches) == 1:
        rel_target = relative_link_target(note, matches[0])
        return converted_result(source_file, line, original_link, rel_target, alias)
    if len(matches) > 1:
        candidates = sorted({item.rel_path for item in matches}, key=str.lower)
        return LinkResult(source_file, line, original_link, ";".join(candidates), "ambiguous", candidates=candidates)
    return LinkResult(source_file, line, original_link, "", "missing")


def converted_result(
    source_file: str,
    line: int,
    original_link: str,
    rel_target: str,
    alias: str | None,
) -> LinkResult:
    if alias is None:
        replacement = f"[[{rel_target}]]"
    else:
        replacement = f"[[{rel_target}|{alias}]]"
    return LinkResult(source_file, line, original_link, rel_target, "converted", replacement_link=replacement)


def split_target_alias(raw_link_body: str) -> tuple[str, str | None]:
    if "|" not in raw_link_body:
        return raw_link_body, None
    target, alias = raw_link_body.split("|", 1)
    return target, alias


def has_markdown_extension(target: str) -> bool:
    return ".md" in target.lower()


def contains_folder(target: str) -> bool:
    return "/" in target or "\\" in target


def resolve_path_target(
    note: NoteFile,
    index: NoteIndex,
    target: str,
    case_sensitive: bool,
) -> list[NoteFile]:
    normalized_target = normalize_rel_path(target)
    candidates: dict[str, NoteFile] = {}

    source_relative = normalize_rel_path(posixpath.join(note.folder, normalized_target))
    for key in {
        normalize_key(source_relative, case_sensitive),
        normalize_key(normalized_target, case_sensitive),
    }:
        for found in index.by_rel_path.get(key, []):
            candidates[str(found.abs_path)] = found

    return list(candidates.values())


def relative_link_target(source_note: NoteFile, target_note: NoteFile) -> str:
    source_folder = source_note.abs_path.parent
    rel_path = os.path.relpath(target_note.abs_path, start=source_folder)
    return rel_path.replace("\\", "/")


def normalize_rel_path(value: str | os.PathLike[str]) -> str:
    text = str(value).replace("\\", "/")
    text = text.lstrip("/")
    normalized = posixpath.normpath(text)
    if normalized == ".":
        return ""
    return normalized


def normalize_key(value: str, case_sensitive: bool) -> str:
    normalized = normalize_rel_path(value)
    if case_sensitive:
        return normalized
    return normalized.lower()


def to_posix(path: Path) -> str:
    text = path.as_posix()
    if text == ".":
        return ""
    return text


def read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return handle.read()


def write_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def apply_replacements(text: str, replacements: list[tuple[int, int, str]]) -> str:
    parts: list[str] = []
    cursor = 0
    for start, end, replacement in replacements:
        parts.append(text[cursor:start])
        parts.append(replacement)
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts)


def write_csv_report(csv_report_file: str | os.PathLike[str], records: list[LinkResult]) -> None:
    with Path(csv_report_file).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source_file", "line", "original_link", "resolved_path", "status"])
        for record in records:
            writer.writerow(
                [
                    record.source_file,
                    record.line,
                    record.original_link,
                    record.resolved_path,
                    record.status,
                ]
            )


def log_record(logger: logging.Logger, record: LinkResult) -> None:
    if record.status == "converted":
        logger.info(
            "CONVERTED %s:%s %s -> %s",
            record.source_file,
            record.line,
            record.original_link,
            record.replacement_link,
        )
    elif record.status == "already_explicit":
        logger.info(
            "ALREADY_EXPLICIT %s:%s %s",
            record.source_file,
            record.line,
            record.original_link,
        )
    elif record.status == "ambiguous":
        logger.info(
            "AMBIGUOUS %s:%s %s candidates=%s",
            record.source_file,
            record.line,
            record.original_link,
            ", ".join(record.candidates),
        )
    elif record.status == "missing":
        logger.info("MISSING %s:%s %s", record.source_file, record.line, record.original_link)


def print_dry_run_change(record: LinkResult) -> None:
    print("-----------------------------------------")
    print("File")
    print(record.source_file)
    print("Line " + str(record.line))
    print("Old")
    print(record.original_link)
    print("New")
    print(record.replacement_link)


def print_ambiguous(record: LinkResult) -> None:
    print("AMBIGUOUS")
    print("File:")
    print("    " + record.source_file)
    print("Link:")
    print("    " + record.original_link)
    print("Candidates:")
    for candidate in record.candidates:
        print(candidate)


def print_missing(record: LinkResult) -> None:
    print("MISSING")
    print("File:")
    print("    " + record.source_file)
    print("Link:")
    print("    " + record.original_link)


def print_summary(summary: Summary) -> None:
    print("Files scanned:")
    print(summary.files_scanned)
    print("Wiki links found:")
    print(summary.wiki_links_found)
    print("Already explicit:")
    print(summary.already_explicit)
    print("Converted:")
    print(summary.converted)
    print("Ambiguous:")
    print(summary.ambiguous)
    print("Missing:")
    print(summary.missing)
    print("Files modified:")
    print(summary.files_modified)


def print_failures(failures: list[str]) -> None:
    print("Failures:")
    for failure in failures:
        print(failure)


if __name__ == "__main__":
    main()
