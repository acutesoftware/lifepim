from __future__ import annotations

from datetime import date
from html.parser import HTMLParser
import re

import requests


SCHOOL_TERMS_URL = (
    "https://www.education.sa.gov.au/students/"
    "term-dates-south-australian-state-schools"
)
_WEEKDAY_RE = re.compile(
    r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b\s*",
    re.IGNORECASE,
)
_MONTHS = {
    month.lower(): number
    for number, month in enumerate(
        (
            "",
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        )
    )
    if month
}


class _TermPageParser(HTMLParser):
    """Collect section headings, list entries, and table rows without extra dependencies."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.section = ""
        self.list_items: list[tuple[str, str]] = []
        self.table_rows: list[tuple[str, list[str]]] = []
        self._heading: list[str] | None = None
        self._list_item: list[str] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "h2":
            self._heading = []
        elif tag == "li":
            self._list_item = []
        elif tag == "tr":
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._heading is not None:
            self._heading.append(data)
        if self._list_item is not None:
            self._list_item.append(data)
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2" and self._heading is not None:
            self.section = _clean_text(" ".join(self._heading))
            self._heading = None
        elif tag == "li" and self._list_item is not None:
            self.list_items.append((self.section, _clean_text(" ".join(self._list_item))))
            self._list_item = None
        elif tag in {"th", "td"} and self._cell is not None and self._row is not None:
            self._row.append(_clean_text(" ".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.table_rows.append((self.section, self._row))
            self._row = None


def fetch_school_terms(timeout: float = 20) -> list[dict]:
    """Download and parse every complete school-term year published by SA Education."""
    try:
        response = requests.get(
            SCHOOL_TERMS_URL,
            timeout=timeout,
            headers={"User-Agent": "LifePIM Desktop school-term importer"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"Could not download SA school term dates: {exc}") from exc
    return parse_school_terms(response.text)


def parse_school_terms(html: str) -> list[dict]:
    parser = _TermPageParser()
    parser.feed(html)
    terms_by_year: dict[int, dict[int, tuple[date, date]]] = {}

    for section, item in parser.list_items:
        year_match = re.fullmatch(r"Term dates for\s+(\d{4})", section, re.IGNORECASE)
        term_match = re.match(r"Term\s*([1-4])\s*[-\u2013\u2014]\s*(.+)", item, re.IGNORECASE)
        if year_match and term_match:
            year = int(year_match.group(1))
            terms_by_year.setdefault(year, {})[int(term_match.group(1))] = _parse_range(
                term_match.group(2), year
            )

    for section, cells in parser.table_rows:
        if "term dates" not in section.lower() or len(cells) < 5:
            continue
        year_text = cells[0].strip()
        if not re.fullmatch(r"\d{4}", year_text):
            continue
        year = int(year_text)
        parsed = {}
        for term_number, cell in enumerate(cells[1:5], start=1):
            parsed[term_number] = _parse_range(cell, year)
        terms_by_year[year] = parsed

    complete_years = {
        year: terms for year, terms in terms_by_year.items() if set(terms) == {1, 2, 3, 4}
    }
    if not complete_years:
        raise ValueError("The SA Education page did not contain any complete school-term years.")

    return [
        {
            "year": year,
            "term": term_number,
            "title": f"School Term {term_number}",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "all_day": 1,
            "blocks_time": 0,
            "event_type": "school_term",
            "category": "SA School Terms",
            "area": "General",
            "status": "active",
            "source": "school_terms_sa",
            "content": "South Australian state school term",
        }
        for year in sorted(complete_years)
        for term_number, (start, end) in sorted(complete_years[year].items())
    ]


def _parse_range(value: str, year: int) -> tuple[date, date]:
    value = _WEEKDAY_RE.sub("", _clean_text(value))
    match = re.search(
        r"(\d{1,2})\s+([A-Za-z]+)(?:\s+\d{4})?\s+to\s+"
        r"(\d{1,2})\s+([A-Za-z]+)(?:\s+\d{4})?",
        value,
        re.IGNORECASE,
    )
    if not match:
        raise ValueError(f"Could not read a school term date range for {year}: {value}")
    try:
        start = date(year, _MONTHS[match.group(2).lower()], int(match.group(1)))
        end = date(year, _MONTHS[match.group(4).lower()], int(match.group(3)))
    except (KeyError, ValueError) as exc:
        raise ValueError(f"Invalid school term date range for {year}: {value}") from exc
    if end < start:
        raise ValueError(f"School term ends before it starts for {year}: {value}")
    return start, end


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()
