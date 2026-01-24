"""Mapping helpers for importer."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple


class MappingError(Exception):
    pass


def extract_source_columns(mapping: Dict[str, Any]) -> List[str]:
    cols: List[str] = []
    for value in mapping.values():
        if isinstance(value, str):
            cols.append(value)
        elif isinstance(value, tuple) and len(value) == 2:
            source_cols = value[0]
            if isinstance(source_cols, (tuple, list)):
                cols.extend([str(col) for col in source_cols])
            else:
                cols.append(str(source_cols))
    return cols


def apply_mapping(row: Dict[str, Any], mapping: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    mapped: Dict[str, Any] = {}
    errors: List[str] = []
    for target_field, spec in mapping.items():
        try:
            mapped[target_field] = _resolve_mapping_value(row, spec)
        except Exception as exc:
            mapped[target_field] = None
            errors.append(f"{target_field}: {exc}")
    return mapped, errors


def _resolve_mapping_value(row: Dict[str, Any], spec: Any) -> Any:
    if spec is None:
        return None
    if isinstance(spec, str):
        return row.get(spec)
    if isinstance(spec, tuple) and len(spec) == 2:
        source_cols, transform = spec
        if isinstance(source_cols, (tuple, list)):
            values = [row.get(col) for col in source_cols]
            return transform(*values)
        return transform(row.get(source_cols))
    return spec
