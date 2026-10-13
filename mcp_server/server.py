from pathlib import Path
import sqlite3

from fastmcp import FastMCP

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "campus_customs_new.db"

mcp = FastMCP("campus_customs")


def _connect():
    return sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)


def _ticket_row_to_dict(row):
    if row is None:
        return None
    return {
        "id": row[0],
        "type": row[1],
        "requester": row[2],
        "subject": row[3],
        "sku": row[4],
        "size": row[5],
        "qty": row[6],
        "lease_id": row[7],
        "invoice_id": row[8],
        "status": row[9],
        "notes": row[10],
        "created_at": row[11],
    }


@mcp.tool()
def customer_order_ticket_101() -> dict:
    """Return the real database details for the open customer order ticket 101."""
    with _connect() as conn:
        ticket = conn.execute(
            """
            SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, notes, created_at
            FROM tickets WHERE id = 101
            """
        ).fetchone()
        sku = ticket[4] if ticket else None
        inventory = []
        if sku:
            inventory = [
                {
                    "sku": row[0],
                    "name": row[1],
                    "size": row[2],
                    "qty": row[3],
                    "location": row[4],
                }
                for row in conn.execute(
                    "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? ORDER BY size",
                    (sku,),
                ).fetchall()
            ]
        pricing = None
        if sku:
            pricing_row = conn.execute(
                "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?",
                (sku,),
            ).fetchone()
            if pricing_row:
                pricing = {
                    "sku": pricing_row[0],
                    "unit_cost": pricing_row[1],
                    "list_price": pricing_row[2],
                }
        invoice = None
        invoice_id = ticket[8] if ticket else None
        if invoice_id is not None:
            invoice_row = conn.execute(
                "SELECT id, vendor_id, amount, due_date, status, description FROM invoices WHERE id = ?",
                (invoice_id,),
            ).fetchone()
            if invoice_row:
                invoice = {
                    "id": invoice_row[0],
                    "vendor_id": invoice_row[1],
                    "amount": invoice_row[2],
                    "due_date": invoice_row[3],
                    "status": invoice_row[4],
                    "description": invoice_row[5],
                }

        return {
            "ticket": _ticket_row_to_dict(ticket),
            "inventory": inventory,
            "pricing": pricing,
            "invoice": invoice,
        }


@mcp.tool()
def rent_notice_ticket_102() -> dict:
    """Return the real database details for the open rent notice ticket 102."""
    with _connect() as conn:
        ticket = conn.execute(
            """
            SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, notes, created_at
            FROM tickets WHERE id = 102
            """
        ).fetchone()
        lease = None
        lease_id = ticket[7] if ticket else None
        if lease_id is not None:
            lease_row = conn.execute(
                "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
                (lease_id,),
            ).fetchone()
            if lease_row:
                lease = {
                    "id": lease_row[0],
                    "space_name": lease_row[1],
                    "landlord": lease_row[2],
                    "monthly_rent": lease_row[3],
                    "next_due": lease_row[4],
                    "notes": lease_row[5],
                }

        return {
            "ticket": _ticket_row_to_dict(ticket),
            "lease": lease,
        }


@mcp.tool()
def price_override_ticket_103() -> dict:
    """Return the real database details for the open price override ticket 103."""
    with _connect() as conn:
        ticket = conn.execute(
            """
            SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, notes, created_at
            FROM tickets WHERE id = 103
            """
        ).fetchone()
        sku = ticket[4] if ticket else None
        inventory = []
        if sku:
            inventory = [
                {
                    "sku": row[0],
                    "name": row[1],
                    "size": row[2],
                    "qty": row[3],
                    "location": row[4],
                }
                for row in conn.execute(
                    "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? ORDER BY size",
                    (sku,),
                ).fetchall()
            ]
        pricing = None
        if sku:
            pricing_row = conn.execute(
                "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?",
                (sku,),
            ).fetchone()
            if pricing_row:
                pricing = {
                    "sku": pricing_row[0],
                    "unit_cost": pricing_row[1],
                    "list_price": pricing_row[2],
                }

        return {
            "ticket": _ticket_row_to_dict(ticket),
            "inventory": inventory,
            "pricing": pricing,
        }


@mcp.tool()
def shop_operations_context() -> dict:
    """Return read-only date, cash, vendor, invoice, and payment context for shop decisions."""
    with _connect() as conn:
        desk_row = conn.execute(
            "SELECT date_today, notes FROM desk ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        desk = (
            {"date_today": desk_row[0], "notes": desk_row[1]}
            if desk_row
            else None
        )
        cash_accounts = [
            {"name": row[0], "balance": row[1], "date": row[2]}
            for row in conn.execute(
                "SELECT name, balance, date FROM cash_accounts ORDER BY name"
            ).fetchall()
        ]
        invoices = [
            {
                "id": row[0],
                "vendor_id": row[1],
                "amount": row[2],
                "due_date": row[3],
                "status": row[4],
                "description": row[5],
            }
            for row in conn.execute(
                "SELECT id, vendor_id, amount, due_date, status, description "
                "FROM invoices ORDER BY id"
            ).fetchall()
        ]
        payments = [
            {
                "id": row[0],
                "kind": row[1],
                "ref_id": row[2],
                "amount": row[3],
                "account": row[4],
                "paid_at": row[5],
                "approved_by": row[6],
            }
            for row in conn.execute(
                "SELECT id, kind, ref_id, amount, account, paid_at, approved_by "
                "FROM payments ORDER BY id"
            ).fetchall()
        ]
        vendors = [
            {
                "id": row[0],
                "name": row[1],
                "specialty": row[2],
                "lead_days": row[3],
            }
            for row in conn.execute(
                "SELECT id, name, specialty, lead_days FROM vendors ORDER BY id"
            ).fetchall()
        ]

        return {
            "desk": desk,
            "cash_accounts": cash_accounts,
            "invoices": invoices,
            "payments": payments,
            "vendors": vendors,
        }


if __name__ == "__main__":
    mcp.run()
