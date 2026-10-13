# Campus Customs Homework 5

- The original database is `data/campus_customs.db` and must never be modified.
- The working copy is `data/campus_customs_new.db`; this is the database the MCP server and backend should use.
- To reset the working copy, run `powershell -ExecutionPolicy Bypass -File .\scripts\reset_working_db.ps1`.
- The reset script fails with a clear error if the original database is missing or empty.
- Every agent must use only the `gpt-6-luna` model through Portkey.
- Keep the Portkey API key in `.env` and do not commit it to source control.

## Clean setup and database reset

The original database is `data/campus_customs.db` and must never be modified. The working database is `data/campus_customs_new.db`. To make a clean working copy before a run, use PowerShell from the repository root:

```powershell
Copy-Item -Force data/campus_customs.db data/campus_customs_new.db
```

The reset script performs the same safe copy and is also available after the backend starts through its reset route:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\reset_working_db.ps1
```

Before a full three-ticket run, reset the working copy, confirm the starting balance, and then run tickets 101, 102, and 103 from the dashboard. Only approve payments when you intend the working balance to change.

## Environment

Copy `.env.example` to `.env` and replace the placeholder locally:

```powershell
Copy-Item .env.example .env
```

Never commit `.env` or share its value.

## Start the MCP server

Install dependencies first if needed:

```powershell
py -3 -m pip install -r requirements.txt
```

The MCP server is configured in `.mcp.json` and `.vscode/mcp.json`. To run it directly from the repository root:

```powershell
py -3 -m mcp_server.server
```

## Agent team

- Install the Python dependencies with `py -3 -m pip install -r requirements.txt`.
- Set a valid `PORTKEY_API_KEY` in `.env` or the process environment. The checked-in project template contains only a placeholder.
- To run one agent when ready, use `py -3 -m backend.run "Boss" "Review ticket 101"`. The available agent names are `Boss`, `Inventory`, `Accounting`, `Facilities`, and `Customer Service`.
- Agent shop data is read only through the MCP server. Run events and MCP/delegation steps append to `output/audit_trail.json`.
- To start the local dashboard API, open a terminal in `backend` and run `py -3 -m uvicorn main:app --reload --port 8000` (`uvicorn` by itself is not on this computer's PATH). Open `http://localhost:8000/docs` to inspect routes. The ticket-agent route runs agents only when explicitly requested. Payment and purchase routes require an explicit approval body; reset only restores the working database copy and requires a confirmation phrase.

## Start the FastAPI backend

From the repository root:

```powershell
py -3 -m uvicorn backend.main:app --reload --port 8000
```

Alternatively, from `backend`:

```powershell
py -3 -m uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000/docs` to inspect the API.

## Start the React board

In a second terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

Open the local URL printed by Vite, usually `http://localhost:5173` (or the next available port).
