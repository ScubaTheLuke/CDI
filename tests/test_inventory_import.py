import io
from decimal import Decimal

import pytest

import inventory_import


def parse(text: str):
    return list(inventory_import.parse_inventory_csv(io.StringIO(text)))


def test_parse_tcgplayer_basic():
    text = (
        "Quantity,Name,Simple Name,Set,Card Number,Set Code,Printing,Condition,Language,Rarity,Product ID,SKU\n"
        "3,Brainstorm,Brainstorm,Ice Age,48,ICE,Normal,Near Mint,English,Common,123,456\n"
    )
    rows = parse(text)
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "Brainstorm"
    assert row["set_code"] == "ICE"
    assert row["quantity"] == 3
    assert row["is_foil"] is False


def test_parse_tcglive_prioritizes_totals():
    text = (
        "TCGplayer Id,Product Line,Set Name,Product Name,Title,Number,Rarity,Condition,TCG Market Price,TCG Direct Low,TCG Low Price With Shipping,TCG Low Price,Total Quantity,Add to Quantity,TCG Marketplace Price,Photo URL\n"
        "123,Magic,Midnight Hunt,Delver of Secrets,,70,U,Near Mint,0.67,,0.75,0.60,0,5,0.58,\n"
    )
    rows = parse(text)
    assert len(rows) == 1
    row = rows[0]
    assert row["quantity"] == 5
    assert row["market_price"] == Decimal("0.67")
    assert row["acquisition_price"] == Decimal("0.58")


def test_parse_unknown_header_raises():
    text = "a,b\n1,2\n"
    with pytest.raises(inventory_import.InventoryImportError):
        parse(text)
