from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentName(str, Enum):
    BOSS = "Boss"
    INVENTORY = "Inventory"
    ACCOUNTING = "Accounting"
    FACILITIES = "Facilities"
    CUSTOMER_SERVICE = "Customer Service"


class TicketRecord(BaseModel):
    id: int
    type: str
    requester: str
    subject: str
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
    lease_id: int | None = None
    invoice_id: int | None = None
    status: str
    notes: str | None = None
    created_at: str


class InventoryRecord(BaseModel):
    sku: str
    name: str
    size: str
    qty: int
    location: str


class PricingRecord(BaseModel):
    sku: str
    unit_cost: float
    list_price: float


class InvoiceRecord(BaseModel):
    id: int
    vendor_id: int
    amount: float
    due_date: str
    status: str
    description: str


class LeaseRecord(BaseModel):
    id: int
    space_name: str
    landlord: str
    monthly_rent: float
    next_due: str
    notes: str | None = None


class DeskRecord(BaseModel):
    date_today: str
    notes: str | None = None


class CashAccountRecord(BaseModel):
    name: str
    balance: float
    date: str


class PaymentRecord(BaseModel):
    id: int
    kind: str
    ref_id: int
    amount: float
    account: str
    paid_at: str
    approved_by: str | None = None


class VendorRecord(BaseModel):
    id: int
    name: str
    specialty: str
    lead_days: int


class ShopOperationsContext(BaseModel):
    desk: DeskRecord | None
    cash_accounts: list[CashAccountRecord] = Field(default_factory=list)
    invoices: list[InvoiceRecord] = Field(default_factory=list)
    payments: list[PaymentRecord] = Field(default_factory=list)
    vendors: list[VendorRecord] = Field(default_factory=list)


class AgentRequest(BaseModel):
    agent: AgentName
    prompt: str = Field(min_length=1)


class TicketRunRequest(BaseModel):
    prompt: str | None = Field(default=None, max_length=2000)


class PaymentApprovalRequest(BaseModel):
    kind: Literal["invoice", "rent"]
    ref_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    account: Literal["checking"] = "checking"
    approved_by: str = Field(min_length=1, max_length=120)
    human_approved: bool = False


class PurchaseApprovalRequest(BaseModel):
    ticket_id: int = Field(gt=0)
    vendor_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    account: Literal["checking"] = "checking"
    approved_by: str = Field(min_length=1, max_length=120)
    human_approved: bool = False


class DatabaseResetRequest(BaseModel):
    confirmation: str


class AgentAnswer(BaseModel):
    agent: AgentName
    run_id: str
    response: str


class AuditEvent(BaseModel):
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    run_id: str
    actor: str
    event: str
    details: dict[str, Any] = Field(default_factory=dict)


@dataclass
class DelegationBudget:
    remaining: int


@dataclass
class AgentDependencies:
    audit: Any
    agents: dict[AgentName, Any]
    run_id: str
    path: tuple[AgentName, ...]
    delegation_budget: DelegationBudget