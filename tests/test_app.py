import importlib
import sys
from decimal import Decimal
from datetime import date
from types import SimpleNamespace

import pytest


class DBStub:
    def __init__(self):
        self.single_cards = []
        self.sealed_products = []
        self.supply_batches = []
        self.sale_events = []
        self.ledger_entries = []
        self.calls = SimpleNamespace(
            add_single_card=[],
            update_single_card=[],
            delete_single_card=[],
            add_sealed_product=[],
            update_sealed_product=[],
            delete_sealed_product=[],
            add_supply_batch=[],
            delete_supply_batch=[],
            record_multi_item_sale=[],
            delete_sale_event=[],
            add_ledger_entry=[],
            delete_ledger_entry=[],
        )

    def fetch_dashboard_summary(self):
        return {"total_supplies_cost": Decimal("5")}

    def list_single_cards(self):
        return self.single_cards

    def list_sealed_products(self):
        return self.sealed_products

    def list_supply_batches(self):
        return self.supply_batches

    def get_all_sale_events_with_items(self):
        return self.sale_events

    def list_ledger_entries(self):
        return self.ledger_entries

    def add_single_card(self, payload):
        self.calls.add_single_card.append(payload)

    def update_single_card(self, card_id, data):
        self.calls.update_single_card.append((card_id, data))

    def delete_single_card(self, card_id):
        self.calls.delete_single_card.append(card_id)

    def add_sealed_product(self, payload):
        self.calls.add_sealed_product.append(payload)

    def update_sealed_product(self, product_id, data):
        self.calls.update_sealed_product.append((product_id, data))

    def delete_sealed_product(self, product_id):
        self.calls.delete_sealed_product.append(product_id)

    def add_supply_batch(self, payload):
        self.calls.add_supply_batch.append(payload)

    def delete_supply_batch(self, batch_id):
        self.calls.delete_supply_batch.append(batch_id)

    def record_multi_item_sale(self, payload):
        self.calls.record_multi_item_sale.append(payload)
        return 123

    def delete_sale_event(self, event_id):
        self.calls.delete_sale_event.append(event_id)

    def add_ledger_entry(self, payload):
        self.calls.add_ledger_entry.append(payload)

    def delete_ledger_entry(self, entry_id):
        self.calls.delete_ledger_entry.append(entry_id)


@pytest.fixture
def app_module(monkeypatch):
    stub = DBStub()
    monkeypatch.setattr("database.Database", lambda: stub)
    sys.modules.pop("app", None)
    app = importlib.import_module("app")
    app.app.config.update(TESTING=True, SECRET_KEY="test")
    return app, stub


@pytest.fixture
def client(app_module, monkeypatch):
    app, stub = app_module
    with app.app.test_client() as client:
        yield client, stub, app


def test_currency_filter_formats_decimal(app_module):
    app, _ = app_module
    assert app.currency_filter(Decimal("12.5")) == "$12.50"


def test_currency_filter_handles_none(app_module):
    app, _ = app_module
    assert app.currency_filter(None) == "$0.00"


def test_date_filter_with_date_object(app_module):
    app, _ = app_module
    today = date(2024, 1, 2)
    assert app.date_filter(today) == "2024-01-02"


def test_date_filter_invalid_string(app_module):
    app, _ = app_module
    assert app.date_filter("not-a-date") == "not-a-date"


def test_index_route_renders(client, monkeypatch):
    test_client, stub, app = client
    monkeypatch.setattr(app, "render_template", lambda *args, **kwargs: "rendered")
    response = test_client.get("/")
    assert response.data == b"rendered"
    assert stub.fetch_dashboard_summary()["total_supplies_cost"] == Decimal("5")


def test_add_single_card_creates_entry(client):
    test_client, stub, _ = client
    response = test_client.post(
        "/inventory/cards/add",
        data={
            "name": "Black Lotus",
            "is_foil": "on",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert stub.calls.add_single_card
    assert stub.calls.add_single_card[0]["is_foil"] is True


def test_bulk_update_cards_updates_each(client):
    test_client, stub, _ = client
    response = test_client.post(
        "/inventory/cards/bulk-update",
        json=[{"id": 1, "quantity": 4}, {"id": 2}],
    )
    assert response.status_code == 200
    assert stub.calls.update_single_card[0] == (1, {"quantity": 4})


def test_delete_card_invokes_db(client):
    test_client, stub, _ = client
    response = test_client.post("/inventory/cards/5/delete")
    assert response.status_code == 302
    assert stub.calls.delete_single_card == [5]


def test_add_sealed_product(client):
    test_client, stub, _ = client
    response = test_client.post(
        "/inventory/sealed/add",
        data={"name": "Sealed Box"},
    )
    assert response.status_code == 302
    assert stub.calls.add_sealed_product


def test_bulk_update_sealed(client):
    test_client, stub, _ = client
    response = test_client.post(
        "/inventory/sealed/bulk-update",
        json=[{"id": 7, "quantity": 2}],
    )
    assert response.status_code == 200
    assert stub.calls.update_sealed_product[0] == (7, {"quantity": 2})


def test_delete_sealed_product(client):
    test_client, stub, _ = client
    response = test_client.post("/inventory/sealed/3/delete")
    assert response.status_code == 302
    assert stub.calls.delete_sealed_product == [3]


def test_add_supply_batch(client):
    test_client, stub, _ = client
    response = test_client.post(
        "/supplies/add",
        data={"description": "Boxes"},
    )
    assert response.status_code == 302
    assert stub.calls.add_supply_batch


def test_delete_supply_batch(client):
    test_client, stub, _ = client
    response = test_client.post("/supplies/8/delete")
    assert response.status_code == 302
    assert stub.calls.delete_supply_batch == [8]


def test_record_sale_success(client):
    test_client, stub, _ = client
    response = test_client.post("/sales/record", json={"items": []})
    assert response.status_code == 200
    assert response.get_json()["sale_id"] == 123
    assert stub.calls.record_multi_item_sale[0] == {"items": []}


def test_delete_sale_event(client):
    test_client, stub, _ = client
    response = test_client.post("/sales/9/delete")
    assert response.status_code == 302
    assert stub.calls.delete_sale_event == [9]


def test_add_ledger_entry(client):
    test_client, stub, _ = client
    response = test_client.post(
        "/ledger/add",
        data={"description": "Income", "amount": "10"},
    )
    assert response.status_code == 302
    assert stub.calls.add_ledger_entry


def test_delete_ledger_entry(client):
    test_client, stub, _ = client
    response = test_client.post("/ledger/4/delete")
    assert response.status_code == 302
    assert stub.calls.delete_ledger_entry == [4]


def test_api_scryfall_search_requires_query(client):
    test_client, _, _ = client
    response = test_client.get("/api/scryfall/search")
    assert response.status_code == 400


def test_api_scryfall_search_success(client, monkeypatch):
    test_client, _, app = client
    monkeypatch.setattr(app.scryfall, "search_cards", lambda q: ["card"])
    response = test_client.get("/api/scryfall/search", query_string={"query": "lotus"})
    assert response.status_code == 200
    assert response.get_json()["data"] == ["card"]
