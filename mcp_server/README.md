# Campus Customs MCP Server

This server provides read-only shop facts for the Campus Customs agent team. It reads `data/campus_customs_new.db` and supports ticket review and draft recommendations without changing the database.

## Database
- Uses: `data/campus_customs_new.db`
- Read-only access only
- The original database remains in `data/campus_customs.db`

## Tools
1. `customer_order_ticket_101` — reads the `tickets`, `inventory`, `pricing`, and `invoices` tables for the open customer order ticket.
2. `rent_notice_ticket_102` — reads the `tickets` and `leases` tables for the open rent notice ticket.
3. `price_override_ticket_103` — reads the `tickets`, `inventory`, and `pricing` tables for the open bulk discount request.
4. `shop_operations_context` — reads the `desk`, `cash_accounts`, `invoices`, `payments`, and `vendors` tables to provide the date and shared shop-policy context.

The PydanticAI agents connect to these tools over stdio using `py -3 -m mcp_server.server`. No backend agent reads the SQLite database directly. MCP tools do not write to either database, send customer messages, place orders, or make payments.
