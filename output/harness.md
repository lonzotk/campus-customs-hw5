# Agent Harness

Simple working notes for the campus customs dataset.

## cash_accounts
Fields: name, balance, date
Why it matters: tracks the money available for payments and cash checks.

## desk
Fields: date_today, notes
Why it matters: holds the daily operational notes for the front desk.

## inventory
Fields: sku, name, size, qty, location
Why it matters: shows stock levels and where each item is stored for fulfillment.

## invoices
Fields: id, vendor_id, amount, due_date, status, description
Why it matters: tracks supplier bills and outstanding payment obligations.

## leases
Fields: id, space_name, landlord, monthly_rent, next_due, notes
Why it matters: records rental commitments and landlord notices tied to the shop.

## payments
Fields: id, kind, ref_id, amount, account, paid_at, approved_by
Why it matters: records approved cash or account payments and their source.

## pricing
Fields: sku, unit_cost, list_price
Why it matters: defines cost and selling price for product decisions and overrides.

## tickets
Fields: id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, notes, created_at
Why it matters: the operational hub for customer issues, rent notices, and pricing requests.

## vendors
Fields: id, name, specialty, lead_days
Why it matters: stores supplier data for restocks, pricing, and invoice follow-up.

## MCP server tools
- `customer_order_ticket_101` — Reads: tickets, inventory, pricing, invoices. Ticket: 101. Why: It connects the open customer order to the requested SKU, stock levels, pricing, and invoice context from the live database.
- `rent_notice_ticket_102` — Reads: tickets, leases. Ticket: 102. Why: It links the open rent notice to the matching lease record so the agent can review the landlord and rent timeline from the real data.
- `price_override_ticket_103` — Reads: tickets, inventory, pricing. Ticket: 103. Why: It matches the bulk hoodie request to the actual product stock and pricing data needed for a real pricing decision.
- `shop_operations_context` — Reads: desk, cash_accounts, invoices, payments, vendors. Why: It supplies the current desk date and shared financial/vendor facts needed to apply shop rules across tickets.

## PydanticAI agent team
All five agents use the `gpt-6-luna` model through Portkey and share the same four read-only MCP tools. The tools listed below are the role-relevant tools for each agent; the shared context tool is available to all. Every agent can ask another agent for help with a bounded delegation tool.

- `Boss` — Coordinates the ticket review. Role-relevant MCP tools: `customer_order_ticket_101`, `rent_notice_ticket_102`, `price_override_ticket_103`, `shop_operations_context`. Tables: tickets, inventory, pricing, invoices, leases, desk, cash_accounts, payments, vendors.
- `Inventory` — Reviews stock, product, and supplier context. Role-relevant MCP tools: `customer_order_ticket_101`, `price_override_ticket_103`, `shop_operations_context`. Tables: tickets, inventory, pricing, desk, cash_accounts, invoices, payments, vendors.
- `Accounting` — Reviews invoices, cash, payment, rent, and price context. Role-relevant MCP tools: `customer_order_ticket_101`, `rent_notice_ticket_102`, `price_override_ticket_103`, `shop_operations_context`. Tables: tickets, inventory, pricing, invoices, leases, desk, cash_accounts, payments, vendors.
- `Facilities` — Reviews the rent notice and lease. Role-relevant MCP tools: `rent_notice_ticket_102`, `shop_operations_context`. Tables: tickets, leases, desk, cash_accounts, invoices, payments, vendors.
- `Customer Service` — Prepares customer-facing drafts for order and pricing requests. Role-relevant MCP tools: `customer_order_ticket_101`, `price_override_ticket_103`, `shop_operations_context`. Tables: tickets, inventory, pricing, desk, cash_accounts, invoices, payments, vendors.

## Safety and limits
- All shop facts must come from the MCP server and `data/campus_customs_new.db`. The server opens that working copy in read-only mode; the original `data/campus_customs.db` is not used by agents.
- Agents use `desk.date_today` as today. If it is missing, they must not guess a date.
- Agents can only recommend or draft. They cannot make or approve payments, change stock, place orders, or send messages to customers. A human must approve every payment.
- Do not recommend a payment that would make any cash account negative. Do not recommend ordering from a vendor with an open unpaid invoice.
- The audit trail appends run start/end/failure, MCP tool start/result/failure, and agent delegation start/result/failure events to `output/audit_trail.json`; it does not clear prior events.
- Per agent run: at most 4 model requests, 6 tool calls, 6,000 input tokens, 900 output tokens, and 6,900 total tokens. A top-level task allows at most 3 cross-agent delegations. These limits do not authorize external actions.
- Every agent is fixed to `gpt-6-luna`. A valid `PORTKEY_API_KEY` must be configured locally before a model run.

## Local FastAPI routes
Start from the `backend` folder with `py -3 -m uvicorn main:app --reload --port 8000`. The bare `uvicorn` command is not on this computer's PATH. The API binds to localhost by default and allows browser requests from localhost/127.0.0.1 origins.

- `GET /health` — Returns API readiness; does not initialize or run agents.
- `GET /tickets` — Returns ticket 101, 102, and 103 with open/resolved status from their MCP ticket tools.
- `GET /tickets/{ticket_id}` — Returns one supported ticket and its MCP details; supported IDs are 101, 102, and 103.
- `POST /tickets/{ticket_id}/run` — Explicitly runs Boss and the agent team for that ticket; accepts an optional prompt. This route is not called automatically at startup.
- `GET /events?limit=50` — Returns recent audit events and per-run summaries with agent statements and MCP tools used.
- `GET /shop/context` — Returns desk date, cash, invoice, payment, and vendor facts through the shared read-only MCP tool.
- `GET /cash/checking` — Returns the checking balance and as-of date from `shop_operations_context` via MCP.
- `POST /approvals/payment` — Pays a full open invoice or rent amount using `{ "kind": "invoice"|"rent", "ref_id": number, "amount": number, "account": "checking", "approved_by": string, "human_approved": true }`. The endpoint checks the full amount, uses `desk.date_today`, prevents duplicate records and negative balances, inserts a `payments` row, and marks a paid invoice as paid.
- `POST /approvals/purchase` — Records an approved purchase cash outflow with `{ "ticket_id": number, "vendor_id": number, "amount": number, "account": "checking", "approved_by": string, "human_approved": true }`. It refuses vendors with an open invoice and records the cash outflow in `payments`; it does not place an order or change inventory.
- `POST /database/reset` — Restores only `data/campus_customs_new.db` from `data/campus_customs.db` using SQLite backup; requires `{ "confirmation": "RESET_WORKING_DATABASE" }`. The source database is opened read-only.

The approval fields represent an explicit UI confirmation, not user authentication. Keep Uvicorn bound to localhost; this API is not suitable for exposure to a network without adding authentication and authorization.

## Recorded ticket runs and resolution evidence
The following summaries use `output/audit_trail.json`, the current working database, and the provided dashboard screenshots in `output/screenshots/`. The screenshots show each ticket as “Resolved in board”; the corresponding database ticket rows still have status `open`.

- Ticket 101 — Run `0117578eb3fe4704a4c6929fe2622bca` completed with Boss only. Boss used `shop_operations_context` and `customer_order_ticket_101`; no specialist handoff is recorded. The run confirmed size S was out of stock and invoice 501 for $840 remained open, and returned a customer draft. No payment is recorded. Screenshot: `output/screenshots/ticket-101.png`.
- Ticket 102 — Run `6cfd39866a194198976b729dcd0a8833` completed with Boss only. Boss used `shop_operations_context` and `rent_notice_ticket_102`; no specialist handoff is recorded. Human approval record `approval-13716dfe5c4b40c3908465a29e93a5d2` records Stefan approving $2,400 rent for lease 1 on 2026-08-31; payment row 1 matches. Screenshot: `output/screenshots/ticket-102.png`.
- Ticket 103 — Run `413beb0d13e946ceb0f8fa36ad3c5953` included Boss and Inventory. Boss used `shop_operations_context` and `price_override_ticket_103`, then delegated the stock-gap/recommendation question to Inventory. Inventory used `price_override_ticket_103` and `shop_operations_context`, then handed back the finding that 8 size-M units were listed against 20 requested, with no approved discount and no identified hoodie vendor. Boss completed the response. No purchase payment is recorded. Screenshot: `output/screenshots/ticket-103.png`.

## Cash reconciliation for recorded runs
- Starting checking balance: $3,400.00 as shown in the pre-payment run context, dated 2026-08-31.
- Ticket 101: $0.00 change; no payment row is recorded.
- Ticket 102: −$2,400.00; rent payment row 1, lease 1, approved by Stefan and paid 2026-08-31.
- Ticket 103: $0.00 change; no purchase payment row is recorded.
- Ending checking balance: $1,000.00 as of 2026-08-31, matching `cash_accounts` in `data/campus_customs_new.db`.
- Structured record: `output/resolved_tickets.json`. Screenshot board: `output/resolved_board.html`.
