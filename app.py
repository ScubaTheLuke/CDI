import io
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from flask import Flask, Response, flash, jsonify, redirect, render_template, request, url_for
from dotenv import load_dotenv

from database import Database
import scryfall
import inventory_import

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret")

db = Database()


@app.template_filter("currency")
def currency_filter(value: Any) -> str:
    if value is None:
        return "$0.00"
    if isinstance(value, Decimal):
        amount = value
    else:
        amount = Decimal(str(value))
    return f"${amount:,.2f}"


@app.template_filter("dateformat")
def date_filter(value: Any, fmt: str = "%Y-%m-%d") -> str:
    if not value:
        return ""
    if isinstance(value, date):
        return value.strftime(fmt)
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value)
    return parsed.strftime(fmt)


@app.route("/")
def index() -> str:
    summary = db.fetch_dashboard_summary()
    cards = db.list_single_cards()
    sealed = db.list_sealed_products()
    supplies = db.list_supply_batches()
    sales = db.get_all_sale_events_with_items()
    ledger_entries = db.list_ledger_entries()
    total_supplies_cost = summary.get("total_supplies_cost", Decimal("0"))
    print(f"Total Shipping Supplies Cost Used in Sales (All Time): {currency_filter(total_supplies_cost)}")
    return render_template(
        "index.html",
        summary=summary,
        cards=cards,
        sealed_products=sealed,
        supply_batches=supplies,
        sale_events=sales,
        ledger_entries=ledger_entries,
        today=date.today(),
    )


@app.post("/inventory/cards/add")
def add_single_card() -> Response:
    form = request.form
    payload = {
        "scryfall_id": form.get("scryfall_id"),
        "name": form.get("name"),
        "set_code": form.get("set_code"),
        "collector_number": form.get("collector_number"),
        "condition": form.get("condition"),
        "language": form.get("language"),
        "is_foil": form.get("is_foil") == "on",
        "acquisition_price": form.get("acquisition_price"),
        "market_price": form.get("market_price"),
        "quantity": form.get("quantity"),
        "acquired_at": form.get("acquired_at"),
        "notes": form.get("notes"),
    }
    try:
        db.add_single_card(payload)
        flash("Single card added to inventory.", "success")
    except Exception as exc:
        flash(f"Failed to add card: {exc}", "error")
    return redirect(url_for("index") + "#inventory")

@app.post("/inventory/cards/bulk-update")
def bulk_update_cards() -> Response:
    updates = request.get_json(force=True)
    if not isinstance(updates, list):
        return jsonify({"error": "Invalid payload"}), 400
    for entry in updates:
        card_id = entry.get("id")
        if not card_id:
            continue
        data = {key: value for key, value in entry.items() if key != "id"}
        try:
            db.update_single_card(int(card_id), data)
        except Exception as exc:
            return jsonify({"error": str(exc), "failed_id": card_id}), 400
    return jsonify({"status": "ok"})


@app.post("/inventory/cards/<int:card_id>/delete")
def delete_card(card_id: int) -> Response:
    try:
        db.delete_single_card(card_id)
        flash("Card deleted.", "success")
    except Exception as exc:
        flash(f"Failed to delete card: {exc}", "error")
    return redirect(url_for("index") + "#inventory")

@app.post("/inventory/cards/import")
def import_card_inventory() -> Response:
    uploaded = request.files.get("inventory_csv")
    if uploaded is None or uploaded.filename == "":
        flash("Select a CSV file to import.", "error")
        return redirect(url_for("index") + "#inventory")

    try:
        uploaded.stream.seek(0)
        raw = uploaded.read()
        if isinstance(raw, bytes):
            text_data = raw.decode("utf-8-sig")
        else:
            text_data = raw
        stream = io.StringIO(text_data)
        imported = 0
        try:
            for payload in inventory_import.parse_inventory_csv(stream):
                db.add_single_card(payload)
                imported += 1
        finally:
            stream.close()
    except inventory_import.InventoryImportError as exc:
        flash(f"CSV import failed: {exc}", "error")
        return redirect(url_for("index") + "#inventory")
    except Exception as exc:
        flash(f"Failed to import CSV: {exc}", "error")
        return redirect(url_for("index") + "#inventory")

    if imported == 0:
        flash("The CSV file did not contain any rows to import.", "warning")
    else:
        flash(f"Imported {imported} card entries.", "success")
    return redirect(url_for("index") + "#inventory")

@app.post("/inventory/sealed/add")
def add_sealed_product() -> Response:
    form = request.form
    payload = {
        "name": form.get("name"),
        "set_code": form.get("set_code"),
        "product_type": form.get("product_type"),
        "acquisition_price": form.get("acquisition_price"),
        "market_price": form.get("market_price"),
        "quantity": form.get("quantity"),
        "acquired_at": form.get("acquired_at"),
        "notes": form.get("notes"),
    }
    try:
        db.add_sealed_product(payload)
        flash("Sealed product added.", "success")
    except Exception as exc:
        flash(f"Failed to add sealed product: {exc}", "error")
    return redirect(url_for("index") + "#inventory")

@app.post("/inventory/sealed/bulk-update")
def bulk_update_sealed() -> Response:
    updates = request.get_json(force=True)
    if not isinstance(updates, list):
        return jsonify({"error": "Invalid payload"}), 400
    for entry in updates:
        product_id = entry.get("id")
        if not product_id:
            continue
        data = {key: value for key, value in entry.items() if key != "id"}
        try:
            db.update_sealed_product(int(product_id), data)
        except Exception as exc:
            return jsonify({"error": str(exc), "failed_id": product_id}), 400
    return jsonify({"status": "ok"})


@app.post("/inventory/sealed/<int:product_id>/delete")
def delete_sealed_product(product_id: int) -> Response:
    try:
        db.delete_sealed_product(product_id)
        flash("Sealed product deleted.", "success")
    except Exception as exc:
        flash(f"Failed to delete sealed product: {exc}", "error")
    return redirect(url_for("index") + "#inventory")

@app.post("/supplies/add")
def add_supply_batch() -> Response:
    form = request.form
    payload = {
        "description": form.get("description"),
        "supplier": form.get("supplier"),
        "unit_cost": form.get("unit_cost"),
        "quantity_purchased": form.get("quantity_purchased"),
        "purchased_at": form.get("purchased_at"),
        "notes": form.get("notes"),
    }
    try:
        db.add_supply_batch(payload)
        flash("Shipping supplies recorded.", "success")
    except Exception as exc:
        flash(f"Failed to add shipping supplies: {exc}", "error")
    return redirect(url_for("index") + "#inventory")

@app.post("/supplies/<int:batch_id>/delete")
def delete_supply_batch(batch_id: int) -> Response:
    try:
        db.delete_supply_batch(batch_id)
        flash("Shipping supply batch deleted.", "success")
    except Exception as exc:
        flash(f"Failed to delete supply batch: {exc}", "error")
    return redirect(url_for("index") + "#inventory")

@app.post("/sales/record")
def record_sale() -> Response:
    payload = request.get_json(force=True)
    try:
        sale_id = db.record_multi_item_sale(payload)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    flash("Sale recorded.", "success")
    return jsonify({"sale_id": sale_id})


@app.post("/sales/<int:event_id>/delete")
def delete_sale(event_id: int) -> Response:
    try:
        db.delete_sale_event(event_id)
        flash("Sale event deleted.", "success")
    except Exception as exc:
        flash(f"Failed to delete sale event: {exc}", "error")
    return redirect(url_for("index") + "#sales")


@app.post("/ledger/add")
def add_ledger_entry() -> Response:
    form = request.form
    payload = {
        "entry_date": form.get("entry_date") or date.today(),
        "description": form.get("description"),
        "amount": form.get("amount"),
        "category": form.get("category"),
    }
    try:
        db.add_ledger_entry(payload)
        flash("Ledger entry added.", "success")
    except Exception as exc:
        flash(f"Failed to add ledger entry: {exc}", "error")
    return redirect(url_for("index") + "#ledger")


@app.post("/ledger/<int:entry_id>/delete")
def delete_ledger_entry(entry_id: int) -> Response:
    try:
        db.delete_ledger_entry(entry_id)
        flash("Ledger entry deleted.", "success")
    except Exception as exc:
        flash(f"Failed to delete ledger entry: {exc}", "error")
    return redirect(url_for("index") + "#ledger")


@app.get("/api/scryfall/search")
def api_scryfall_search() -> Response:
    query = request.args.get("query")
    if not query:
        return jsonify({"error": "Query parameter required"}), 400
    try:
        results = scryfall.search_cards(query)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify({"data": results})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)), debug=True)

