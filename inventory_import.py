import csv
from decimal import Decimal
from enum import Enum
from typing import Dict, Iterator, Optional, TextIO


class InventoryImportError(Exception):
    """Raised when a CSV file cannot be parsed."""


class InventoryFileType(Enum):
    TCGPLAYER = "tcgplayer"
    TCGLIVE = "tcglive"
def parse_inventory_csv(handle: TextIO) -> Iterator[Dict[str, object]]:
    reader = csv.DictReader(handle)
    if reader.fieldnames is None:
        raise InventoryImportError("CSV file is missing a header row.")

    header_map = {
        _normalize_header(name): name for name in reader.fieldnames if name is not None
    }
    file_type = _detect_file_type(header_map)

    for row in reader:
        if not row:
            continue
        if not any((value or "").strip() for value in row.values()):
            continue
        if file_type is InventoryFileType.TCGPLAYER:
            parsed = _parse_tcgplayer_row(row, header_map)
        else:
            parsed = _parse_tcglive_row(row, header_map)
        if parsed is None:
            continue
        yield parsed


def _detect_file_type(header_map: Dict[str, str]) -> InventoryFileType:
    headers = set(header_map.keys())
    if {"quantity", "name", "set code", "card number", "printing", "condition"}.issubset(headers):
        return InventoryFileType.TCGPLAYER
    if {"tcgplayer id", "product name", "set name", "total quantity", "condition"}.issubset(headers):
        return InventoryFileType.TCGLIVE
    raise InventoryImportError("Unrecognized CSV header layout.")


def _parse_tcgplayer_row(row: Dict[str, str], header_map: Dict[str, str]) -> Optional[Dict[str, object]]:
    name = _field(row, header_map, "name") or _field(row, header_map, "simple name")
    if not name or not name.strip():
        return None

    quantity = _parse_int(_field(row, header_map, "quantity"))
    if quantity <= 0:
        return None

    printing = (_field(row, header_map, "printing") or "").strip().lower()
    is_foil = "foil" in printing and "non" not in printing

    payload: Dict[str, object] = {
        "scryfall_id": None,
        "name": name.strip(),
        "set_code": _field(row, header_map, "set code") or _field(row, header_map, "set"),
        "collector_number": _field(row, header_map, "card number"),
        "condition": _field(row, header_map, "condition"),
        "language": _field(row, header_map, "language") or "English",
        "is_foil": is_foil,
        "acquisition_price": Decimal("0"),
        "market_price": Decimal("0"),
        "quantity": quantity,
        "acquired_at": None,
        "notes": None,
    }
    return payload


def _parse_tcglive_row(row: Dict[str, str], header_map: Dict[str, str]) -> Optional[Dict[str, object]]:
    name = _field(row, header_map, "product name") or _field(row, header_map, "title")
    if not name or not name.strip():
        return None

    quantity = _parse_int(_field(row, header_map, "total quantity"))
    if quantity <= 0:
        quantity = _parse_int(_field(row, header_map, "add to quantity"))
    if quantity <= 0:
        return None

    title_text = (name or "") + " " + (_field(row, header_map, "title") or "")
    title_text = title_text.lower()
    is_foil = "foil" in title_text and "non" not in title_text

    acquisition_price = _parse_decimal(
        _field(row, header_map, "tcg marketplace price")
        or _field(row, header_map, "tcg low price")
        or _field(row, header_map, "tcg low price with shipping")
    )
    market_price = _parse_decimal(_field(row, header_map, "tcg market price"))

    payload: Dict[str, object] = {
        "scryfall_id": None,
        "name": name.strip(),
        "set_code": _field(row, header_map, "set name"),
        "collector_number": _field(row, header_map, "number"),
        "condition": _field(row, header_map, "condition"),
        "language": "English",
        "is_foil": is_foil,
        "acquisition_price": acquisition_price,
        "market_price": market_price,
        "quantity": quantity,
        "acquired_at": None,
        "notes": None,
    }
    return payload


def _field(row: Dict[str, str], header_map: Dict[str, str], key: str) -> Optional[str]:
    actual = header_map.get(key)
    if not actual:
        return None
    return row.get(actual)


def _parse_int(value: Optional[str]) -> int:
    if value is None:
        return 0
    value = value.strip()
    if not value:
        return 0
    try:
        return int(float(value))
    except ValueError:
        return 0


def _parse_decimal(value: Optional[str]) -> Decimal:
    if not value:
        return Decimal("0")
    cleaned = value.replace("$", "").replace(",", "").strip()
    if not cleaned:
        return Decimal("0")
    try:
        return Decimal(cleaned)
    except Exception:
        return Decimal("0")


def _normalize_header(header: str) -> str:
    return " ".join(header.strip().lstrip("\ufeff").lower().split())


