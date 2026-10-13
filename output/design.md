# Campus Customs Dashboard Design

## Layout

The dashboard is an operations desk rather than a marketing page. A persistent dark-green rail holds the shop identity, ticket navigation, team roster, and connection status. The main workspace gives the ticket queue and selected ticket the most room, with a narrower inspector for checking cash, linked ticket facts, and MCP tools used. On smaller screens, the rail becomes a compact header and the queue, ticket, and inspector stack into a single column.

The selected ticket stays visible beside the agent activity feed. The activity feed polls the backend audit endpoint while a run is active, making MCP calls and agent handoffs visible as they happen. The final recommendation and each completed delegation response remain available as the run summary.

## Agent identities

Each agent has a distinct monogram and restrained color so a handoff is scannable without turning the roster into decoration. Boss uses olive, Inventory teal, Accounting ochre, Facilities slate-blue, and Customer Service coral. The same identity treatment appears in the sidebar roster and live activity feed, so the speaker remains clear while the team works.

## Resolved tickets and cash

A successful run marks its ticket resolved in the dashboard and persists that display state in this browser. It does not alter the ticket record in SQLite; the original database remains untouched and the database status is shown separately from the board status.

The checking balance is presented in a deep-green cash panel with its desk-date timestamp and refreshes from the backend. An approval form appears only when the completed agent response indicates that approval is being requested. The person must enter their name and check an explicit approval box before the frontend submits an invoice, rent, or purchase approval. The backend remains responsible for checking funds and enforcing the vendor-invoice rule. No email, order placement, or agent run is triggered by loading the page.

## Rationale

The dense three-part workspace reduces context switching during ticket review: queue first, work in the center, and relevant money/data at the edge. Muted paper tones keep long-running operational data readable; green identifies the shop and safe/connected states, while coral, ochre, and blue separate agent roles and exceptional ticket context. Status and confirmation are stated in text as well as color. The narrower mobile layout preserves the ticket details and approval controls without relying on hover or desktop-only interactions.
