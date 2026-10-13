from __future__ import annotations

import json
import math
import sqlite3
import sys
import uuid
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.audit import AuditTrail, DEFAULT_AUDIT_PATH
from backend.models import (
    AgentName,
    AgentRequest,
    DatabaseResetRequest,
    PaymentApprovalRequest,
    PurchaseApprovalRequest,
    TicketRunRequest,
)
from backend.team import AgentTeam, build_team


WORKING_DB = PROJECT_ROOT / "data" / "campus_customs_new.db"
ORIGINAL_DB = PROJECT_ROOT / "data" / "campus_customs.db"
TICKET_TO_TOOL = {
    101: "customer_order_ticket_101",
    102: "rent_notice_ticket_102",
    103: "price_override_ticket_103",
}
DB_RESET_CONFIRMATION = "RESET_WORKING_DATABASE"

app = FastAPI(
    title="Campus Customs Desk API",
    version="1.0.0",
    description="Local API for ticket review and human-approved cash operations.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

_audit = AuditTrail(DEFAULT_AUDIT_PATH)
_team: AgentTeam | None = None


def _mcp_transport() -> StdioTransport:
    return StdioTransport(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        cwd=str(PROJECT_ROOT),
    )


async def _call_shop_tools(tool_names: list[str]) -> dict[str, dict[str, Any]]:
    try:
        async with Client(_mcp_transport(), name="campus_customs_api", timeout=30) as client:
            available = {tool.name for tool in await client.list_tools()}
            missing = sorted(set(tool_names) - available)
            if missing:
                raise RuntimeError(f"MCP server is missing tools: {', '.join(missing)}")
            results: dict[str, dict[str, Any]] = {}
            for tool_name in tool_names:
                result = await client.call_tool(tool_name, {})
                if result.is_error or result.structured_content is None:
                    raise RuntimeError(f"MCP tool returned no structured data: {tool_name}")
                results[tool_name] = result.structured_content
            return results
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"Could not read shop data from the campus_customs MCP server: {error}",
        ) from error


def _ticket_view(tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
    ticket = result.get("ticket")
    if not isinstance(ticket, dict):
        raise HTTPException(status_code=404, detail="Ticket was not found in the MCP response.")
    database_status = str(ticket.get("status", "unknown")).strip().lower()
    status = "resolved" if database_status in {"resolved", "closed", "complete", "completed"} else "open"
    return {
        **ticket,
        "status": status,
        "database_status": database_status,
        "mcp_tool": tool_name,
        "details": {key: value for key, value in result.items() if key != "ticket"},
    }


def _read_audit_events(limit: int) -> list[dict[str, Any]]:
    audit_path = _audit.path
    if not audit_path.exists():
        return []
    try:
        events = json.loads(audit_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=500, detail=f"Could not read audit trail: {error}") from error
    if not isinstance(events, list):
        raise HTTPException(status_code=500, detail="Audit trail must contain a JSON array.")
    return [event for event in events[-limit:] if isinstance(event, dict)]


def _audit_run_summary(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        run_id = event.get("run_id")
        if run_id:
            grouped[str(run_id)].append(event)

    summaries: list[dict[str, Any]] = []
    for run_id, run_events in grouped.items():
        statements = [
            {
                "agent": event.get("details", {}).get("target_agent", event.get("actor")),
                "said": event.get("details", {}).get("response"),
            }
            for event in run_events
            if event.get("event") in {"agent.run.completed", "agent.delegation.completed"}
        ]
        tools = []
        for event in run_events:
            if event.get("event") == "mcp_tool.started":
                tool_name = event.get("details", {}).get("tool_name")
                if tool_name and tool_name not in tools:
                    tools.append(tool_name)
        summaries.append(
            {
                "run_id": run_id,
                "started_at": run_events[0].get("timestamp"),
                "agents": list(dict.fromkeys(event.get("actor") for event in run_events)),
                "statements": statements,
                "tools_used": tools,
                "events": run_events,
            }
        )
    return summaries


def _connect_working_db() -> sqlite3.Connection:
    if not WORKING_DB.is_file() or WORKING_DB.stat().st_size == 0:
        raise HTTPException(status_code=503, detail="Working database is missing or empty.")
    connection = sqlite3.connect(WORKING_DB, timeout=10, isolation_level=None)
    connection.row_factory = sqlite3.Row
    return connection


def _require_human_approval(approved: bool, approved_by: str) -> None:
    if not approved or not approved_by.strip():
        raise HTTPException(
            status_code=400,
            detail="Explicit human_approved=true and a non-empty approved_by name are required.",
        )


def _audit_approval(kind: str, reference: int, amount: Decimal, approved_by: str) -> None:
    _audit.record(
        run_id=f"approval-{uuid.uuid4().hex}",
        actor=approved_by.strip(),
        event="cash.approval.completed",
        details={"kind": kind, "ref_id": reference, "amount": str(amount), "account": "checking"},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tickets")
async def list_tickets() -> list[dict[str, Any]]:
    tool_names = list(TICKET_TO_TOOL.values())
    results = await _call_shop_tools(tool_names)
    return [_ticket_view(tool_name, results[tool_name]) for tool_name in tool_names]


@app.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: int) -> dict[str, Any]:
    tool_name = TICKET_TO_TOOL.get(ticket_id)
    if tool_name is None:
        raise HTTPException(status_code=404, detail="Only tickets 101, 102, and 103 are available.")
    result = await _call_shop_tools([tool_name])
    return _ticket_view(tool_name, result[tool_name])


@app.post("/tickets/{ticket_id}/run")
async def run_ticket_agent(
    ticket_id: int,
    request: TicketRunRequest | None = None,
) -> dict[str, Any]:
    tool_name = TICKET_TO_TOOL.get(ticket_id)
    if tool_name is None:
        raise HTTPException(status_code=404, detail="Only tickets 101, 102, and 103 can be run.")
    await _call_shop_tools([tool_name])
    global _team
    if _team is None:
        try:
            _team = build_team()
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"Could not initialize agent team: {error}") from error
    prompt = request.prompt.strip() if request and request.prompt else ""
    if not prompt:
        prompt = (
            f"Review open ticket {ticket_id}. Use the relevant campus_customs MCP tools, "
            "follow your safety instructions, ask only necessary specialists for help, "
            "and return a recommendation or draft for human review. Do not take external action."
        )
    try:
        answer = await _team.run(AgentRequest(agent=AgentName.BOSS, prompt=prompt))
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Agent run failed: {error}") from error
    events = [event for event in _read_audit_events(200) if event.get("run_id") == answer.run_id]
    summary = _audit_run_summary(events)
    return {
        "run_id": answer.run_id,
        "ticket_id": ticket_id,
        "agent": answer.agent.value,
        "response": answer.response,
        "tools_used": summary[0]["tools_used"] if summary else [],
    }


@app.get("/events")
async def recent_agent_events(
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    events = _read_audit_events(limit)
    return {"events": events, "runs": _audit_run_summary(events)}


@app.get("/shop/context")
async def shop_context() -> dict[str, Any]:
    result = await _call_shop_tools(["shop_operations_context"])
    return result["shop_operations_context"]


@app.get("/cash/checking")
async def checking_balance() -> dict[str, Any]:
    result = await _call_shop_tools(["shop_operations_context"])
    context = result["shop_operations_context"]
    accounts = context.get("cash_accounts", [])
    checking = next((account for account in accounts if account.get("name") == "checking"), None)
    if checking is None:
        raise HTTPException(status_code=404, detail="Checking account was not found in MCP data.")
    return {"account": "checking", "balance": checking["balance"], "as_of": checking["date"]}


def _perform_cash_outflow(
    connection: sqlite3.Connection,
    *,
    kind: str,
    reference: int,
    amount: Decimal,
    approved_by: str,
    duplicate_date_only: bool = False,
) -> dict[str, Any]:
    desk = connection.execute("SELECT date_today FROM desk ORDER BY rowid DESC LIMIT 1").fetchone()
    if desk is None or not desk["date_today"]:
        raise HTTPException(status_code=409, detail="desk.date_today is missing; payment date cannot be verified.")
    paid_at = str(desk["date_today"])
    query = "SELECT id FROM payments WHERE kind = ? AND ref_id = ?"
    parameters: tuple[Any, ...] = (kind, reference)
    if duplicate_date_only:
        query += " AND paid_at = ?"
        parameters += (paid_at,)
    if connection.execute(query, parameters).fetchone():
        raise HTTPException(status_code=409, detail=f"A {kind} payment for this reference is already recorded.")

    account = connection.execute(
        "SELECT balance FROM cash_accounts WHERE name = 'checking'"
    ).fetchone()
    if account is None:
        raise HTTPException(status_code=404, detail="Checking account was not found.")
    balance = Decimal(str(account["balance"]))
    if balance < amount:
        raise HTTPException(
            status_code=409,
            detail=f"Insufficient checking funds: available {balance:.2f}, requested {amount:.2f}.",
        )
    cursor = connection.execute(
        "UPDATE cash_accounts SET balance = balance - ? WHERE name = 'checking' AND balance >= ?",
        (float(amount), float(amount)),
    )
    if cursor.rowcount != 1:
        raise HTTPException(status_code=409, detail="Checking balance changed; approval was not applied.")
    cursor = connection.execute(
        "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
        "VALUES (?, ?, ?, 'checking', ?, ?)",
        (kind, reference, float(amount), paid_at, approved_by.strip()),
    )
    return {
        "payment_id": cursor.lastrowid,
        "kind": kind,
        "ref_id": reference,
        "amount": float(amount),
        "account": "checking",
        "paid_at": paid_at,
        "approved_by": approved_by.strip(),
        "balance": float(balance - amount),
    }


@app.post("/approvals/payment")
async def approve_payment(request: PaymentApprovalRequest) -> dict[str, Any]:
    _require_human_approval(request.human_approved, request.approved_by)
    with closing(_connect_working_db()) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            if request.kind == "invoice":
                invoice = connection.execute(
                    "SELECT amount, status FROM invoices WHERE id = ?", (request.ref_id,)
                ).fetchone()
                if invoice is None:
                    raise HTTPException(status_code=404, detail="Invoice was not found.")
                if str(invoice["status"]).lower() != "open":
                    raise HTTPException(status_code=409, detail="Only an open invoice can be paid.")
                if not math.isclose(float(invoice["amount"]), float(request.amount), abs_tol=0.005):
                    raise HTTPException(status_code=422, detail="Payment amount must match the full invoice amount.")
                payment_kind = "invoice"
            else:
                lease = connection.execute(
                    "SELECT monthly_rent FROM leases WHERE id = ?", (request.ref_id,)
                ).fetchone()
                if lease is None:
                    raise HTTPException(status_code=404, detail="Lease was not found.")
                if not math.isclose(float(lease["monthly_rent"]), float(request.amount), abs_tol=0.005):
                    raise HTTPException(status_code=422, detail="Payment amount must match the full monthly rent amount.")
                payment_kind = "rent"

            payment = _perform_cash_outflow(
                connection,
                kind=payment_kind,
                reference=request.ref_id,
                amount=request.amount,
                approved_by=request.approved_by,
                duplicate_date_only=payment_kind == "rent",
            )
            if payment_kind == "invoice":
                connection.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (request.ref_id,))
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
    _audit_approval(payment_kind, request.ref_id, request.amount, request.approved_by)
    return payment


@app.post("/approvals/purchase")
async def approve_purchase(request: PurchaseApprovalRequest) -> dict[str, Any]:
    _require_human_approval(request.human_approved, request.approved_by)
    with closing(_connect_working_db()) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            ticket = connection.execute(
                "SELECT sku, qty, status FROM tickets WHERE id = ?", (request.ticket_id,)
            ).fetchone()
            if ticket is None or not ticket["sku"] or not ticket["qty"]:
                raise HTTPException(status_code=422, detail="Purchase approval requires a product ticket with a SKU and quantity.")
            if str(ticket["status"]).lower() not in {"open", "pending"}:
                raise HTTPException(status_code=409, detail="Only an open product ticket can be used for a purchase.")
            vendor = connection.execute("SELECT id FROM vendors WHERE id = ?", (request.vendor_id,)).fetchone()
            if vendor is None:
                raise HTTPException(status_code=404, detail="Vendor was not found.")
            open_invoice = connection.execute(
                "SELECT id FROM invoices WHERE vendor_id = ? AND lower(status) = 'open' LIMIT 1",
                (request.vendor_id,),
            ).fetchone()
            if open_invoice:
                raise HTTPException(
                    status_code=409,
                    detail=f"Vendor {request.vendor_id} has open unpaid invoice {open_invoice['id']}; purchase approval is blocked.",
                )
            payment = _perform_cash_outflow(
                connection,
                kind="purchase",
                reference=request.ticket_id,
                amount=request.amount,
                approved_by=request.approved_by,
            )
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
    _audit_approval("purchase", request.ticket_id, request.amount, request.approved_by)
    return {**payment, "vendor_id": request.vendor_id, "note": "Cash recorded; this route does not place an order or change inventory."}


@app.post("/database/reset")
async def reset_working_database(request: DatabaseResetRequest) -> dict[str, str]:
    if request.confirmation != DB_RESET_CONFIRMATION:
        raise HTTPException(
            status_code=400,
            detail=f"Type {DB_RESET_CONFIRMATION} exactly to reset the working database.",
        )
    if not ORIGINAL_DB.is_file() or ORIGINAL_DB.stat().st_size == 0:
        raise HTTPException(status_code=503, detail="Original database is missing or empty; reset refused.")
    if ORIGINAL_DB.resolve() == WORKING_DB.resolve():
        raise HTTPException(status_code=500, detail="Original and working database paths must differ.")
    try:
        WORKING_DB.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(f"{ORIGINAL_DB.resolve().as_uri()}?mode=ro", uri=True)) as source:
            with closing(sqlite3.connect(WORKING_DB, timeout=30)) as target:
                source.backup(target)
                integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
                if integrity != "ok":
                    raise RuntimeError(f"Reset copy integrity check failed: {integrity}")
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not reset the working database: {error}") from error
    _audit.record(
        run_id=f"reset-{uuid.uuid4().hex}",
        actor="human",
        event="database.working_copy.reset",
        details={"source": str(ORIGINAL_DB), "target": str(WORKING_DB)},
    )
    return {"status": "reset", "message": "Working database restored from the original; original database was opened read-only."}