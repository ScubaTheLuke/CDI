import os
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


def _connection_params() -> Dict[str, Any]:
    return {
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "dbname": os.getenv("DB_NAME"),
    }


def _database_url() -> Optional[str]:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    return None


def get_connection():
    url = _database_url()
    if url:
        extra_kwargs: Dict[str, Any] = {}
        sslmode = os.getenv("DB_SSLMODE", "require")
        if sslmode and "sslmode=" not in url:
            extra_kwargs["sslmode"] = sslmode
        return psycopg2.connect(url, **extra_kwargs)

    params = _connection_params()
    missing = [key for key, value in params.items() if not value]
    if missing:
        raise RuntimeError(f"Missing database configuration for: {', '.join(missing)}")
    return psycopg2.connect(**params)


@contextmanager
def connection_cursor(commit: bool = False):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
            if commit:
                conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database() -> None:
    statements: List[str] = [
        """
        CREATE TABLE IF NOT EXISTS inventory_cards (
            id SERIAL PRIMARY KEY,
            scryfall_id TEXT,
            name TEXT NOT NULL,
            set_code TEXT,
            collector_number TEXT,
            condition TEXT,
            language TEXT,
            is_foil BOOLEAN DEFAULT FALSE,
            acquisition_price NUMERIC(12, 2) NOT NULL DEFAULT 0,
            market_price NUMERIC(12, 2) NOT NULL DEFAULT 0,
            quantity INTEGER NOT NULL DEFAULT 0,
            acquired_at DATE,
            notes TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS sealed_products (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            set_code TEXT,
            product_type TEXT,
            acquisition_price NUMERIC(12, 2) NOT NULL DEFAULT 0,
            market_price NUMERIC(12, 2) NOT NULL DEFAULT 0,
            quantity INTEGER NOT NULL DEFAULT 0,
            acquired_at DATE,
            notes TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS shipping_supply_batches (
            id SERIAL PRIMARY KEY,
            description TEXT NOT NULL,
            supplier TEXT,
            unit_cost NUMERIC(12, 2) NOT NULL,
            quantity_purchased INTEGER NOT NULL,
            quantity_available INTEGER NOT NULL,
            purchased_at DATE NOT NULL,
            notes TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS ledger_entries (
            id SERIAL PRIMARY KEY,
            entry_date DATE NOT NULL,
            description TEXT NOT NULL,
            amount NUMERIC(14, 2) NOT NULL,
            category TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS sale_events (
            id SERIAL PRIMARY KEY,
            sale_date DATE NOT NULL,
            platform TEXT,
            customer_shipping_charged NUMERIC(12, 2) NOT NULL DEFAULT 0,
            actual_postage_cost NUMERIC(12, 2) NOT NULL DEFAULT 0,
            platform_fees NUMERIC(12, 2) NOT NULL DEFAULT 0,
            total_sale_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
            total_cost_of_goods NUMERIC(14, 2) NOT NULL DEFAULT 0,
            total_supplies_cost_for_sale NUMERIC(14, 2) NOT NULL DEFAULT 0,
            total_profit_loss NUMERIC(14, 2) NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS sale_items (
            id SERIAL PRIMARY KEY,
            sale_event_id INTEGER NOT NULL REFERENCES sale_events(id) ON DELETE CASCADE,
            inventory_type TEXT NOT NULL,
            inventory_id INTEGER,
            item_name TEXT NOT NULL,
            set_code TEXT,
            quantity INTEGER NOT NULL,
            sale_price_per_unit NUMERIC(12, 2) NOT NULL,
            acquisition_price_per_unit NUMERIC(12, 2) NOT NULL DEFAULT 0,
            profit_loss NUMERIC(12, 2) NOT NULL DEFAULT 0
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS sale_supplies (
            id SERIAL PRIMARY KEY,
            sale_event_id INTEGER NOT NULL REFERENCES sale_events(id) ON DELETE CASCADE,
            supply_batch_id INTEGER NOT NULL REFERENCES shipping_supply_batches(id),
            quantity_used INTEGER NOT NULL,
            unit_cost NUMERIC(12, 2) NOT NULL,
            total_cost NUMERIC(14, 2) NOT NULL
        );
        """,
        """
        ALTER TABLE sale_events
        ADD COLUMN IF NOT EXISTS customer_shipping_charged NUMERIC(12, 2) NOT NULL DEFAULT 0;
        """,
        """
        ALTER TABLE sale_events
        ADD COLUMN IF NOT EXISTS actual_postage_cost NUMERIC(12, 2) NOT NULL DEFAULT 0;
        """,
        """
        ALTER TABLE sale_events
        ADD COLUMN IF NOT EXISTS platform_fees NUMERIC(12, 2) NOT NULL DEFAULT 0;
        """,
        """
        ALTER TABLE sale_events
        ADD COLUMN IF NOT EXISTS total_sale_amount NUMERIC(14, 2) NOT NULL DEFAULT 0;
        """,
        """
        ALTER TABLE sale_events
        ADD COLUMN IF NOT EXISTS total_cost_of_goods NUMERIC(14, 2) NOT NULL DEFAULT 0;
        """,
        """
        ALTER TABLE sale_events
        ADD COLUMN IF NOT EXISTS total_supplies_cost_for_sale NUMERIC(14, 2) NOT NULL DEFAULT 0;
        """,
        """
        ALTER TABLE sale_events
        ADD COLUMN IF NOT EXISTS total_profit_loss NUMERIC(14, 2) NOT NULL DEFAULT 0;
        """,
        """
        ALTER TABLE sale_events
        ADD COLUMN IF NOT EXISTS notes TEXT;
        """,
        """
        ALTER TABLE inventory_cards
        ADD COLUMN IF NOT EXISTS acquisition_price NUMERIC(12, 2) NOT NULL DEFAULT 0;
        """,
        """
        ALTER TABLE inventory_cards
        ADD COLUMN IF NOT EXISTS market_price NUMERIC(12, 2) NOT NULL DEFAULT 0;
        """,
        """
        ALTER TABLE sealed_products
        ADD COLUMN IF NOT EXISTS acquisition_price NUMERIC(12, 2) NOT NULL DEFAULT 0;
        """,
        """
        ALTER TABLE sealed_products
        ADD COLUMN IF NOT EXISTS market_price NUMERIC(12, 2) NOT NULL DEFAULT 0;
        """,
    ]

    with connection_cursor(commit=True) as cur:
        for statement in statements:
            cur.execute(statement)


def _now() -> datetime:
    return datetime.utcnow()


def _to_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    return Decimal(value)


class Database:
    def __init__(self) -> None:
        initialize_database()

    def list_single_cards(self) -> List[Dict[str, Any]]:
        with connection_cursor() as cur:
            cur.execute(
                """
                SELECT * FROM inventory_cards
                ORDER BY LOWER(name), set_code NULLS LAST, collector_number NULLS LAST
                """
            )
            return [dict(row) for row in cur.fetchall()]

    def add_single_card(self, payload: Dict[str, Any]) -> int:
        columns = [
            "scryfall_id",
            "name",
            "set_code",
            "collector_number",
            "condition",
            "language",
            "is_foil",
            "acquisition_price",
            "market_price",
            "quantity",
            "acquired_at",
            "notes",
        ]
        values = [payload.get(col) for col in columns]
        with connection_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO inventory_cards (
                    scryfall_id, name, set_code, collector_number, condition, language,
                    is_foil, acquisition_price, market_price, quantity, acquired_at, notes,
                    created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                [
                    payload.get("scryfall_id"),
                    payload.get("name"),
                    payload.get("set_code"),
                    payload.get("collector_number"),
                    payload.get("condition"),
                    payload.get("language"),
                    payload.get("is_foil", False),
                    _to_decimal(payload.get("acquisition_price")),
                    _to_decimal(payload.get("market_price")),
                    int(payload.get("quantity", 0)),
                    payload.get("acquired_at"),
                    payload.get("notes"),
                    _now(),
                    _now(),
                ],
            )
            return cur.fetchone()["id"]

    def update_single_card(self, card_id: int, payload: Dict[str, Any]) -> None:
        columns = []
        values: List[Any] = []
        for key, value in payload.items():
            if key not in {
                "scryfall_id",
                "name",
                "set_code",
                "collector_number",
                "condition",
                "language",
                "is_foil",
                "acquisition_price",
                "market_price",
                "quantity",
                "acquired_at",
                "notes",
            }:
                continue
            columns.append(f"{key} = %s")
            if key in {"acquisition_price", "market_price"}:
                values.append(_to_decimal(value))
            elif key == "is_foil":
                values.append(bool(value))
            elif key == "quantity":
                values.append(int(value))
            else:
                values.append(value)
        if not columns:
            return
        values.append(_now())
        values.append(card_id)
        with connection_cursor(commit=True) as cur:
            cur.execute(
                f"""
                UPDATE inventory_cards
                SET {', '.join(columns)}, updated_at = %s
                WHERE id = %s
                """
            , values)

    def delete_single_card(self, card_id: int) -> None:
        with connection_cursor(commit=True) as cur:
            cur.execute("DELETE FROM inventory_cards WHERE id = %s", (card_id,))

    def list_sealed_products(self) -> List[Dict[str, Any]]:
        with connection_cursor() as cur:
            cur.execute(
                """
                SELECT * FROM sealed_products
                ORDER BY LOWER(name)
                """
            )
            return [dict(row) for row in cur.fetchall()]

    def add_sealed_product(self, payload: Dict[str, Any]) -> int:
        with connection_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO sealed_products (
                    name, set_code, product_type, acquisition_price, market_price,
                    quantity, acquired_at, notes, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                [
                    payload.get("name"),
                    payload.get("set_code"),
                    payload.get("product_type"),
                    _to_decimal(payload.get("acquisition_price")),
                    _to_decimal(payload.get("market_price")),
                    int(payload.get("quantity", 0)),
                    payload.get("acquired_at"),
                    payload.get("notes"),
                    _now(),
                    _now(),
                ],
            )
            return cur.fetchone()["id"]

    def update_sealed_product(self, product_id: int, payload: Dict[str, Any]) -> None:
        columns = []
        values: List[Any] = []
        for key, value in payload.items():
            if key not in {
                "name",
                "set_code",
                "product_type",
                "acquisition_price",
                "market_price",
                "quantity",
                "acquired_at",
                "notes",
            }:
                continue
            columns.append(f"{key} = %s")
            if key in {"acquisition_price", "market_price"}:
                values.append(_to_decimal(value))
            elif key == "quantity":
                values.append(int(value))
            else:
                values.append(value)
        if not columns:
            return
        values.append(_now())
        values.append(product_id)
        with connection_cursor(commit=True) as cur:
            cur.execute(
                f"""
                UPDATE sealed_products
                SET {', '.join(columns)}, updated_at = %s
                WHERE id = %s
                """
            , values)

    def delete_sealed_product(self, product_id: int) -> None:
        with connection_cursor(commit=True) as cur:
            cur.execute("DELETE FROM sealed_products WHERE id = %s", (product_id,))

    def list_supply_batches(self) -> List[Dict[str, Any]]:
        with connection_cursor() as cur:
            cur.execute(
                """
                SELECT * FROM shipping_supply_batches
                ORDER BY purchased_at DESC, id DESC
                """
            )
            return [dict(row) for row in cur.fetchall()]

    def add_supply_batch(self, payload: Dict[str, Any]) -> int:
        quantity = int(payload.get("quantity_purchased", 0))
        unit_cost = _to_decimal(payload.get("unit_cost"))
        with connection_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO shipping_supply_batches (
                    description, supplier, unit_cost, quantity_purchased,
                    quantity_available, purchased_at, notes, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                [
                    payload.get("description"),
                    payload.get("supplier"),
                    unit_cost,
                    quantity,
                    quantity,
                    payload.get("purchased_at"),
                    payload.get("notes"),
                    _now(),
                    _now(),
                ],
            )
            batch_id = cur.fetchone()["id"]
        total_cost = unit_cost * Decimal(quantity)
        self.add_ledger_entry(
            {
                "entry_date": payload.get("purchased_at") or date.today(),
                "description": f"Shipping supplies: {payload.get('description')}",
                "amount": (-total_cost) if total_cost != 0 else Decimal("0"),
                "category": "Shipping Supplies",
            }
        )
        return batch_id

    def update_supply_batch(self, batch_id: int, payload: Dict[str, Any]) -> None:
        columns = []
        values: List[Any] = []
        for key, value in payload.items():
            if key not in {
                "description",
                "supplier",
                "unit_cost",
                "quantity_purchased",
                "quantity_available",
                "purchased_at",
                "notes",
            }:
                continue
            columns.append(f"{key} = %s")
            if key in {"unit_cost"}:
                values.append(_to_decimal(value))
            elif key in {"quantity_purchased", "quantity_available"}:
                values.append(int(value))
            else:
                values.append(value)
        if not columns:
            return
        values.append(_now())
        values.append(batch_id)
        with connection_cursor(commit=True) as cur:
            cur.execute(
                f"""
                UPDATE shipping_supply_batches
                SET {', '.join(columns)}, updated_at = %s
                WHERE id = %s
                """
            , values)

    def delete_supply_batch(self, batch_id: int) -> None:
        with connection_cursor(commit=True) as cur:
            cur.execute("DELETE FROM shipping_supply_batches WHERE id = %s", (batch_id,))

    def add_ledger_entry(self, payload: Dict[str, Any]) -> int:
        with connection_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO ledger_entries (entry_date, description, amount, category)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                [
                    payload.get("entry_date") or date.today(),
                    payload.get("description"),
                    _to_decimal(payload.get("amount")),
                    payload.get("category"),
                ],
            )
            return cur.fetchone()["id"]

    def list_ledger_entries(self) -> List[Dict[str, Any]]:
        with connection_cursor() as cur:
            cur.execute(
                """
                SELECT * FROM ledger_entries
                ORDER BY entry_date DESC, id DESC
                """
            )
            return [dict(row) for row in cur.fetchall()]

    def delete_ledger_entry(self, entry_id: int) -> None:
        with connection_cursor(commit=True) as cur:
            cur.execute("DELETE FROM ledger_entries WHERE id = %s", (entry_id,))

    def _get_inventory_record(self, inventory_type: str, inventory_id: int) -> Dict[str, Any]:
        table = "inventory_cards" if inventory_type == "single" else "sealed_products"
        with connection_cursor() as cur:
            cur.execute(f"SELECT * FROM {table} WHERE id = %s", (inventory_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Inventory record not found for {inventory_type}:{inventory_id}")
            return dict(row)

    def _adjust_inventory_quantity(self, inventory_type: str, inventory_id: int, delta: int) -> None:
        table = "inventory_cards" if inventory_type == "single" else "sealed_products"
        with connection_cursor(commit=True) as cur:
            cur.execute(
                f"""
                UPDATE {table}
                SET quantity = quantity + %s, updated_at = %s
                WHERE id = %s
                RETURNING quantity
                """,
                (delta, _now(), inventory_id),
            )
            result = cur.fetchone()
            if not result:
                raise ValueError(f"Inventory record not found for {inventory_type}:{inventory_id}")
            if result["quantity"] < 0:
                raise ValueError("Inventory quantity cannot be negative")

    def _consume_supply(self, supply_batch_id: int, quantity: int) -> Decimal:
        with connection_cursor(commit=True) as cur:
            cur.execute(
                """
                UPDATE shipping_supply_batches
                SET quantity_available = quantity_available - %s, updated_at = %s
                WHERE id = %s
                RETURNING unit_cost, quantity_available
                """,
                (quantity, _now(), supply_batch_id),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("Supply batch not found")
            if row["quantity_available"] < 0:
                raise ValueError("Not enough supplies available")
            return _to_decimal(row["unit_cost"]) * Decimal(quantity)

    def record_multi_item_sale(self, payload: Dict[str, Any]) -> int:
        sale_date = payload.get("sale_date") or date.today()
        items = payload.get("items", [])
        supplies = payload.get("supplies", [])
        if not items:
            raise ValueError("At least one sale item is required")

        inventory_snapshots: List[Dict[str, Any]] = []
        for item in items:
            record = self._get_inventory_record(item["inventory_type"], int(item["inventory_id"]))
            inventory_snapshots.append(record)

        total_sale_amount = Decimal("0")
        total_cost_of_goods = Decimal("0")
        sale_items_rows: List[Dict[str, Any]] = []

        for item, record in zip(items, inventory_snapshots):
            quantity = int(item.get("quantity", 0))
            sale_price_each = _to_decimal(item.get("sale_price_per_unit"))
            total_sale_amount += sale_price_each * Decimal(quantity)
            acquisition_price = _to_decimal(record.get("acquisition_price"))
            total_cost_of_goods += acquisition_price * Decimal(quantity)
            sale_items_rows.append(
                {
                    "inventory_type": item["inventory_type"],
                    "inventory_id": record["id"],
                    "item_name": record["name"],
                    "set_code": record.get("set_code"),
                    "quantity": quantity,
                    "sale_price_per_unit": sale_price_each,
                    "acquisition_price_per_unit": acquisition_price,
                }
            )

        total_supplies_cost = Decimal("0")
        supplies_rows: List[Dict[str, Any]] = []
        for supply in supplies:
            quantity = int(supply.get("quantity_used", 0))
            if quantity <= 0:
                continue
            batch_id = int(supply.get("supply_batch_id"))
            cost = self._consume_supply(batch_id, quantity)
            unit_cost = (cost / Decimal(quantity)) if quantity else Decimal("0")
            total_supplies_cost += cost
            supplies_rows.append(
                {
                    "supply_batch_id": batch_id,
                    "quantity_used": quantity,
                    "unit_cost": unit_cost,
                    "total_cost": cost,
                }
            )

        total_sale_amount += _to_decimal(payload.get("customer_shipping_charged"))
        actual_postage_cost = _to_decimal(payload.get("actual_postage_cost"))
        platform_fees = _to_decimal(payload.get("platform_fees"))

        total_profit = (
            total_sale_amount
            - total_cost_of_goods
            - actual_postage_cost
            - platform_fees
            - total_supplies_cost
        )

        with connection_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO sale_events (
                    sale_date, platform, customer_shipping_charged, actual_postage_cost,
                    platform_fees, total_sale_amount, total_cost_of_goods,
                    total_supplies_cost_for_sale, total_profit_loss, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                [
                    sale_date,
                    payload.get("platform"),
                    _to_decimal(payload.get("customer_shipping_charged")),
                    actual_postage_cost,
                    platform_fees,
                    total_sale_amount,
                    total_cost_of_goods,
                    total_supplies_cost,
                    total_profit,
                    payload.get("notes"),
                ],
            )
            sale_event_id = cur.fetchone()["id"]

        for item_row in sale_items_rows:
            self._adjust_inventory_quantity(
                item_row["inventory_type"], item_row["inventory_id"], -item_row["quantity"]
            )
            profit = (
                item_row["sale_price_per_unit"] - item_row["acquisition_price_per_unit"]
            ) * Decimal(item_row["quantity"])
            with connection_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO sale_items (
                        sale_event_id, inventory_type, inventory_id, item_name, set_code,
                        quantity, sale_price_per_unit, acquisition_price_per_unit, profit_loss
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        sale_event_id,
                        item_row["inventory_type"],
                        item_row["inventory_id"],
                        item_row["item_name"],
                        item_row["set_code"],
                        item_row["quantity"],
                        item_row["sale_price_per_unit"],
                        item_row["acquisition_price_per_unit"],
                        profit,
                    ],
                )

        for supply_row in supplies_rows:
            with connection_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO sale_supplies (
                        sale_event_id, supply_batch_id, quantity_used, unit_cost, total_cost
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    [
                        sale_event_id,
                        supply_row["supply_batch_id"],
                        supply_row["quantity_used"],
                        supply_row["unit_cost"],
                        supply_row["total_cost"],
                    ],
                )

        return sale_event_id

    def _restock_from_sale_items(self, sale_event_id: int) -> None:
        with connection_cursor() as cur:
            cur.execute(
                """
                SELECT inventory_type, inventory_id, quantity
                FROM sale_items
                WHERE sale_event_id = %s
                """,
                (sale_event_id,),
            )
            items = cur.fetchall()
        for item in items:
            self._adjust_inventory_quantity(
                item["inventory_type"], int(item["inventory_id"]), int(item["quantity"])
            )

        with connection_cursor() as cur:
            cur.execute(
                """
                SELECT supply_batch_id, quantity_used
                FROM sale_supplies
                WHERE sale_event_id = %s
                """,
                (sale_event_id,),
            )
            supplies = cur.fetchall()
        for supply in supplies:
            self._adjust_supply_quantity(int(supply["supply_batch_id"]), int(supply["quantity_used"]))

    def _adjust_supply_quantity(self, supply_batch_id: int, delta: int) -> None:
        with connection_cursor(commit=True) as cur:
            sql = (
                "UPDATE shipping_supply_batches "
                "SET quantity_available = quantity_available + %s, updated_at = %s "
                "WHERE id = %s "
                "RETURNING quantity_available, quantity_purchased"
            )
            cur.execute(sql, (delta, _now(), supply_batch_id))
            row = cur.fetchone()
            if not row:
                raise ValueError("Supply batch not found")
            if row["quantity_available"] < 0:
                raise ValueError("Not enough supplies available")
            if row["quantity_available"] > row["quantity_purchased"]:
                raise ValueError("Supply quantity exceeds purchased amount")

    def delete_sale_event(self, sale_event_id: int) -> None:
        self._restock_from_sale_items(sale_event_id)
        with connection_cursor(commit=True) as cur:
            cur.execute("DELETE FROM sale_events WHERE id = %s", (sale_event_id,))

    def get_all_sale_events_with_items(self) -> List[Dict[str, Any]]:
        with connection_cursor() as cur:
            cur.execute(
                """
                SELECT * FROM sale_events
                ORDER BY sale_date DESC, id DESC
                """
            )
            events = [dict(row) for row in cur.fetchall()]
        for event in events:
            with connection_cursor() as cur:
                cur.execute(
                    "SELECT * FROM sale_items WHERE sale_event_id = %s ORDER BY id",
                    (event["id"],),
                )
                event["items"] = [dict(row) for row in cur.fetchall()]
            with connection_cursor() as cur:
                cur.execute(
                    "SELECT * FROM sale_supplies WHERE sale_event_id = %s ORDER BY id",
                    (event["id"],),
                )
                event["supplies"] = [dict(row) for row in cur.fetchall()]
        return events

    def fetch_dashboard_summary(self) -> Dict[str, Decimal]:
        with connection_cursor() as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(SUM(acquisition_price * quantity), 0) AS total_buy_cost,
                    COALESCE(SUM(market_price * quantity), 0) AS total_market_value,
                    COALESCE(SUM(quantity), 0) AS total_quantity
                FROM inventory_cards
                """
            )
            card_metrics = cur.fetchone()

        with connection_cursor() as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(SUM(acquisition_price * quantity), 0) AS total_buy_cost,
                    COALESCE(SUM(market_price * quantity), 0) AS total_market_value,
                    COALESCE(SUM(quantity), 0) AS total_quantity
                FROM sealed_products
                """
            )
            sealed_metrics = cur.fetchone()

        with connection_cursor() as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(SUM(total_sale_amount), 0) AS gross_sales,
                    COALESCE(SUM(total_cost_of_goods), 0) AS total_cogs,
                    COALESCE(SUM(total_profit_loss), 0) AS total_profit,
                    COALESCE(SUM(total_supplies_cost_for_sale), 0) AS supplies_cost,
                    COALESCE(SUM(
                        CASE WHEN date_trunc('month', sale_date) = date_trunc('month', CURRENT_DATE)
                             THEN total_sale_amount ELSE 0 END
                    ), 0) AS current_month_sales,
                    COALESCE(SUM(
                        CASE WHEN date_trunc('month', sale_date) = date_trunc('month', CURRENT_DATE)
                             THEN total_profit_loss ELSE 0 END
                    ), 0) AS current_month_profit
                FROM sale_events
                """
            )
            sale_metrics = cur.fetchone()

        with connection_cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(amount), 0) AS ledger_total FROM ledger_entries"
            )
            ledger_total = cur.fetchone()["ledger_total"]

        net_business_pl = (
            _to_decimal(ledger_total)
            + _to_decimal(sale_metrics["total_profit"])
            + _to_decimal(sale_metrics["supplies_cost"])
        )

        return {
            "single_card_buy_cost": _to_decimal(card_metrics["total_buy_cost"]),
            "single_card_market_value": _to_decimal(card_metrics["total_market_value"]),
            "single_card_quantity": int(card_metrics["total_quantity"] or 0),
            "sealed_buy_cost": _to_decimal(sealed_metrics["total_buy_cost"]),
            "sealed_market_value": _to_decimal(sealed_metrics["total_market_value"]),
            "sealed_quantity": int(sealed_metrics["total_quantity"] or 0),
            "gross_sales": _to_decimal(sale_metrics["gross_sales"]),
            "total_cogs": _to_decimal(sale_metrics["total_cogs"]),
            "total_profit": _to_decimal(sale_metrics["total_profit"]),
            "net_business_pl": net_business_pl,
            "current_month_sales": _to_decimal(sale_metrics["current_month_sales"]),
            "current_month_profit": _to_decimal(sale_metrics["current_month_profit"]),
            "total_supplies_cost": _to_decimal(sale_metrics["supplies_cost"]),
        }


if __name__ == "__main__":
    initialize_database()
    print("Database schema ensured.")
