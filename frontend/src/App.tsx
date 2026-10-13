import { useEffect, useState, type FormEvent } from 'react'
import {
  Activity,
  Check,
  CheckCircle2,
  ChevronRight,
  Circle,
  Clock3,
  CreditCard,
  FileText,
  Landmark,
  LoaderCircle,
  MessageSquareText,
  PackageCheck,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Wallet,
} from 'lucide-react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const AGENTS = [
  { name: 'Boss', title: 'Shop lead', color: 'boss', mark: 'B' },
  { name: 'Inventory', title: 'Stock & sourcing', color: 'inventory', mark: 'I' },
  { name: 'Accounting', title: 'Cash & invoices', color: 'accounting', mark: 'A' },
  { name: 'Facilities', title: 'Lease & space', color: 'facilities', mark: 'F' },
  { name: 'Customer Service', title: 'Customer drafts', color: 'service', mark: 'C' },
]

type Ticket = {
  id: number
  type: string
  requester: string
  subject: string
  sku?: string | null
  size?: string | null
  qty?: number | null
  status: 'open' | 'resolved'
  database_status: string
  notes?: string | null
  created_at?: string
  details?: Record<string, any>
}

type AuditEvent = {
  timestamp?: string
  run_id?: string
  actor?: string
  event: string
  details: Record<string, any>
}

type RunResponse = {
  run_id: string
  ticket_id: number
  agent: string
  response: string
  tools_used: string[]
}

type ShopContext = {
  desk?: { date_today?: string } | null
  cash_accounts: { name: string; balance: number; date: string }[]
  invoices: { id: number; vendor_id: number; amount: number; status: string; description: string }[]
  vendors: { id: number; name: string; specialty: string; lead_days: number }[]
}

type ApprovalKind = 'invoice' | 'rent' | 'purchase'
type RunState = 'idle' | 'running' | 'complete' | 'error'

const ticketHeading = (ticket: Ticket) => {
  if (ticket.id === 101) return 'Bulldog tee · size S'
  if (ticket.id === 102) return 'Shop rent due'
  if (ticket.id === 103) return 'Bulk hoodie discount'
  return ticket.subject
}

const ticketDetail = (ticket: Ticket) => {
  if (ticket.id === 101) return '1 × Classic Bulldog Tee'
  if (ticket.id === 102) return 'Chapel Street shop'
  if (ticket.id === 103) return '20 × Basic Hoodie · size M'
  return ticket.subject
}

const agentColor = (name?: string) => AGENTS.find((agent) => agent.name === name)?.color ?? 'boss'

const eventCopy = (event: AuditEvent) => {
  const details = event.details ?? {}
  switch (event.event) {
    case 'agent.run.started':
      return 'Started ticket review'
    case 'mcp_tool.started':
      return `Calling ${details.tool_name ?? 'MCP tool'}`
    case 'mcp_tool.completed':
      return `Received ${details.tool_name ?? 'MCP result'}`
    case 'agent.delegation.started':
      return `Asked ${details.target_agent ?? 'a teammate'} for help`
    case 'agent.delegation.completed':
      return `Got a response from ${details.target_agent ?? 'a teammate'}`
    case 'agent.run.completed':
      return 'Finished review'
    case 'agent.run.failed':
    case 'agent.delegation.failed':
      return 'Hit an error'
    default:
      return event.event.replaceAll('.', ' ')
  }
}

const isApprovalRequested = (text: string) =>
  /human approval|approval (?:is )?(?:needed|required|requested)|requires? (?:human )?approval|payment draft|purchase draft|ready for approval/i.test(text)

const loadResolvedTickets = (): number[] => {
  try {
    const value: unknown = JSON.parse(localStorage.getItem('campus-customs-resolved') ?? '[]')
    return Array.isArray(value) ? value.filter((id): id is number => typeof id === 'number') : []
  } catch {
    return []
  }
}

async function getJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, options)
  const data = await response.json()
  if (!response.ok) throw new Error(data.detail ?? `Request failed (${response.status})`)
  return data as T
}

function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [context, setContext] = useState<ShopContext | null>(null)
  const [checking, setChecking] = useState<{ balance: number; as_of: string } | null>(null)
  const [selectedId, setSelectedId] = useState(101)
  const [resolvedIds, setResolvedIds] = useState<number[]>(loadResolvedTickets)
  const [runState, setRunState] = useState<RunState>('idle')
  const [runEvents, setRunEvents] = useState<AuditEvent[]>([])
  const [runResult, setRunResult] = useState<RunResponse | null>(null)
  const [runError, setRunError] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [approvalKind, setApprovalKind] = useState<ApprovalKind>('invoice')
  const [purchaseVendor, setPurchaseVendor] = useState('')
  const [purchaseAmount, setPurchaseAmount] = useState('')
  const [approver, setApprover] = useState('')
  const [humanApproved, setHumanApproved] = useState(false)
  const [approvalBusy, setApprovalBusy] = useState(false)
  const [approvalMessage, setApprovalMessage] = useState('')
  const [loadError, setLoadError] = useState('')

  const selectedTicket = tickets.find((ticket) => ticket.id === selectedId)
  const resolved = selectedTicket
    ? resolvedIds.includes(selectedTicket.id) || selectedTicket.status === 'resolved'
    : false
  const involvedAgents = new Set(
    runEvents.flatMap((event) => [event.actor, event.details?.target_agent].filter(Boolean) as string[]),
  )
  const latestAction = [...runEvents].reverse().find((event) =>
    ['agent.run.started', 'mcp_tool.started', 'agent.delegation.started', 'agent.delegation.completed'].includes(event.event),
  )
  const activeAgent = runState === 'running'
    ? latestAction?.event === 'agent.delegation.started'
      ? String(latestAction.details?.target_agent ?? latestAction.actor ?? '')
      : String(latestAction?.actor ?? 'Boss')
    : ''
  const usedTools = Array.from(new Set(
    runEvents
      .filter((event) => event.event === 'mcp_tool.started')
      .map((event) => String(event.details?.tool_name ?? ''))
      .filter(Boolean),
  ))
  const responseText = runResult?.response ?? ''
  const approvalMentioned = runState === 'complete' && isApprovalRequested(responseText)

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      setRefreshing(true)
      setLoadError('')
      try {
        const [ticketData, shopData, balanceData] = await Promise.all([
          getJson<Ticket[]>('/tickets', { signal: controller.signal }),
          getJson<ShopContext>('/shop/context', { signal: controller.signal }),
          getJson<{ balance: number; as_of: string }>('/cash/checking', { signal: controller.signal }),
        ])
        setTickets(ticketData)
        setContext(shopData)
        setChecking(balanceData)
      } catch (error) {
        if (!controller.signal.aborted) setLoadError(error instanceof Error ? error.message : 'Could not connect to the desk API.')
      } finally {
        if (!controller.signal.aborted) setRefreshing(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem('campus-customs-resolved', JSON.stringify(resolvedIds))
    } catch {
      // Keep the resolution state for this session if browser storage is unavailable.
    }
  }, [resolvedIds])

  const refreshDesk = async () => {
    setRefreshing(true)
    setLoadError('')
    try {
      const [ticketData, shopData, balanceData] = await Promise.all([
        getJson<Ticket[]>('/tickets'),
        getJson<ShopContext>('/shop/context'),
        getJson<{ balance: number; as_of: string }>('/cash/checking'),
      ])
      setTickets(ticketData)
      setContext(shopData)
      setChecking(balanceData)
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : 'Could not refresh the desk.')
    } finally {
      setRefreshing(false)
    }
  }

  const startRun = async () => {
    if (!selectedTicket || runState === 'running') return
    setRunState('running')
    setRunError('')
    setRunResult(null)
    setRunEvents([])
    setApprovalMessage('')
    setHumanApproved(false)
    const startedAfter = Date.now() - 1500
    let requestFinished = false
    let result: RunResponse | undefined
    let requestError: unknown

    const requestPromise = getJson<RunResponse>(`/tickets/${selectedTicket.id}/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    }).then(
      (value) => { result = value },
      (error: unknown) => { requestError = error },
    ).finally(() => { requestFinished = true })

    while (!requestFinished) {
      try {
        const data = await getJson<{ events: AuditEvent[] }>('/events?limit=100')
        const matchingEvents = data.events.filter((event) =>
          event.timestamp && Date.parse(event.timestamp) >= startedAfter,
        )
        const startEvent = matchingEvents.find((event) => event.event === 'agent.run.started')
        const runId = startEvent?.run_id
        const currentEvents = runId
          ? matchingEvents.filter((event) => event.run_id === runId)
          : matchingEvents
        if (currentEvents.length) setRunEvents(currentEvents)
      } catch {
        // Keep polling; the final run request reports any API failure.
      }
      if (!requestFinished) await new Promise((resolve) => window.setTimeout(resolve, 800))
    }
    await requestPromise

    if (requestError) {
      setRunState('error')
      setRunError(requestError instanceof Error ? requestError.message : 'The run did not complete.')
      return
    }
    if (!result) {
      setRunState('error')
      setRunError('The API finished without returning a run result.')
      return
    }

    setRunResult(result)
    setRunState('complete')
    setResolvedIds((previous) => previous.includes(selectedTicket.id) ? previous : [...previous, selectedTicket.id])
    try {
      const finalEvents = await getJson<{ events: AuditEvent[] }>('/events?limit=100')
      setRunEvents(finalEvents.events.filter((event) => event.run_id === result?.run_id))
    } catch {
      // Keep the latest progress snapshot if the event refresh fails.
    }
    await refreshDesk()
  }

  const approveTransaction = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!selectedTicket || !humanApproved || !approver.trim()) return
    setApprovalBusy(true)
    setApprovalMessage('')
    try {
      const body = approvalKind === 'purchase'
        ? {
            ticket_id: selectedTicket.id,
            vendor_id: Number(purchaseVendor),
            amount: Number(purchaseAmount),
            account: 'checking',
            approved_by: approver.trim(),
            human_approved: true,
          }
        : {
            kind: approvalKind,
            ref_id: approvalKind === 'invoice'
              ? Number(selectedTicket.details?.invoice?.id)
              : Number(selectedTicket.details?.lease?.id),
            amount: approvalKind === 'invoice'
              ? Number(selectedTicket.details?.invoice?.amount)
              : Number(selectedTicket.details?.lease?.monthly_rent),
            account: 'checking',
            approved_by: approver.trim(),
            human_approved: true,
          }
      const path = approvalKind === 'purchase' ? '/approvals/purchase' : '/approvals/payment'
      const result = await getJson<{ balance: number; amount: number }>(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      setApprovalMessage(`Approved $${Number(result.amount).toFixed(2)}. Checking balance is now $${Number(result.balance).toLocaleString('en-US', { minimumFractionDigits: 2 })}.`)
      setHumanApproved(false)
      await refreshDesk()
    } catch (error) {
      setApprovalMessage(error instanceof Error ? error.message : 'Approval was not recorded.')
    } finally {
      setApprovalBusy(false)
    }
  }

  const selectTicket = (ticketId: number) => {
    const ticket = tickets.find((item) => item.id === ticketId)
    setSelectedId(ticketId)
    if (ticket?.id === 101 && ticket.details?.invoice) setApprovalKind('invoice')
    else if (ticket?.id === 102 && ticket.details?.lease) setApprovalKind('rent')
    else if (ticket?.id === 103) setApprovalKind('purchase')
    setHumanApproved(false)
    setRunState('idle')
    setRunEvents([])
    setRunResult(null)
    setRunError('')
    setApprovalMessage('')
  }

  const selectedInvoice = selectedTicket?.details?.invoice
  const selectedLease = selectedTicket?.details?.lease
  const checkingBalance = Number(checking?.balance ?? 0)
  const checkingDate = checking?.as_of ?? context?.desk?.date_today ?? '—'
  const meterWidth = `${Math.min(100, Math.max(0, (checkingBalance / 5000) * 100))}%`

  return (
    <div className="desk-app">
      <aside className="sidebar">
        <a className="brand" href="#desk" aria-label="Campus Customs desk home">
          <span className="brand-stamp">CC</span>
          <span className="brand-name">Campus<br />Customs</span>
        </a>
        <div className="sidebar-rule" />
        <div className="nav-caption">Front office</div>
        <button className="side-link side-link-active" type="button">
          <Activity size={17} strokeWidth={1.8} /> <span>Ticket desk</span><span className="side-count">03</span>
        </button>
        <div className="side-link side-link-static"><Wallet size={17} strokeWidth={1.8} /><span>Approvals</span></div>
        <div className="nav-caption nav-caption-spaced">Team on call</div>
        <div className="sidebar-team">
          {AGENTS.map((agent) => (
            <div className="sidebar-agent" key={agent.name}>
              <span className={`agent-monogram ${agent.color}`}>{agent.mark}</span>
              <span>{agent.name}</span>
              <span className="presence-dot" />
            </div>
          ))}
        </div>
        <div className="sidebar-bottom">
          <div className="connection-indicator"><span className="connection-dot" /><span>Backend connected</span></div>
          <div className="sidebar-local">Local workspace<br /><span>New Haven, CT</span></div>
        </div>
      </aside>

      <main className="main-area" id="desk">
        <header className="topbar">
          <div className="breadcrumb">Operations <ChevronRight size={13} /> Front desk</div>
          <div className="topbar-actions">
            <span className="today-chip"><span className="today-dot" /> Desk date&nbsp; {context?.desk?.date_today ?? checkingDate}</span>
            <button className="icon-button" type="button" title="Refresh desk data" aria-label="Refresh desk data" onClick={() => void refreshDesk()} disabled={refreshing}>
              <RefreshCw size={16} className={refreshing ? 'spin' : ''} />
            </button>
            <div className="user-stamp" title="Human operator">H</div>
          </div>
        </header>

        <div className="page-heading">
          <div>
            <div className="overline">Campus store operations</div>
            <h1>Good morning, operator<span className="title-period">.</span></h1>
            <p>Three open tickets. The team is ready when you are.</p>
          </div>
          <div className="header-note"><span className="note-mark">✳</span><span>Nothing moves without<br />your say-so.</span></div>
        </div>

        {loadError && <div className="error-banner" role="alert"><ShieldCheck size={17} /> <span>{loadError}</span><button type="button" onClick={() => void refreshDesk()}>Retry</button></div>}

        <div className="workbench">
          <section className="queue-column" aria-labelledby="queue-heading">
            <div className="section-header">
              <div><div className="overline">Work queue</div><h2 id="queue-heading">Open tickets <span className="count-bubble">{tickets.filter((ticket) => !resolvedIds.includes(ticket.id) && ticket.status !== 'resolved').length.toString().padStart(2, '0')}</span></h2></div>
              <button className="quiet-icon" title="Refresh tickets" aria-label="Refresh tickets" type="button" onClick={() => void refreshDesk()}><RefreshCw size={15} /></button>
            </div>
            <div className="ticket-list">
              {tickets.map((ticket, index) => {
                const isResolved = resolvedIds.includes(ticket.id) || ticket.status === 'resolved'
                return (
                  <button
                    className={`ticket-card ${selectedId === ticket.id ? 'ticket-card-selected' : ''} ${isResolved ? 'ticket-card-resolved' : ''}`}
                    key={ticket.id}
                    type="button"
                    onClick={() => selectTicket(ticket.id)}
                    aria-current={selectedId === ticket.id ? 'true' : undefined}
                  >
                    <span className={`ticket-number ${ticket.id === 101 ? 'number-coral' : ticket.id === 102 ? 'number-blue' : 'number-gold'}`}>{String(index + 1).padStart(2, '0')}</span>
                    <span className="ticket-card-main">
                      <span className="ticket-card-top"><span className="ticket-id">#{ticket.id}</span><span className={`status-dot ${isResolved ? 'status-dot-resolved' : ''}`} /></span>
                      <strong>{ticketHeading(ticket)}</strong>
                      <span className="ticket-requester">{ticket.requester}</span>
                      <span className={`ticket-state ${isResolved ? 'resolved-text' : ''}`}>{isResolved ? <><Check size={12} /> Resolved in board</> : 'Needs review'}</span>
                    </span>
                    <ChevronRight size={16} className="ticket-chevron" />
                  </button>
                )
              })}
              {!tickets.length && !loadError && <div className="queue-empty">Loading tickets…</div>}
            </div>
            <div className="queue-footnote"><ShieldCheck size={15} /><span>Read-only ticket data<br /><b>Actions need your approval</b></span></div>
          </section>

          <section className="ticket-workspace" aria-live="polite">
            {selectedTicket ? <>
              <div className="ticket-work-header">
                <div className="ticket-work-id"><span className="ticket-type-mark">{selectedTicket.id === 101 ? <MessageSquareText size={18} /> : selectedTicket.id === 102 ? <Landmark size={18} /> : <PackageCheck size={18} />}</span><span>Ticket #{selectedTicket.id}</span><span className="dot-separator">·</span><span>{selectedTicket.type.replaceAll('_', ' ')}</span></div>
                <span className={`work-status ${resolved ? 'work-status-resolved' : ''}`}>{resolved ? <CheckCircle2 size={14} /> : <Circle size={11} />}{resolved ? 'Resolved' : 'Open'}</span>
              </div>
              <h2 className="ticket-main-title">{ticketHeading(selectedTicket)}</h2>
              <p className="ticket-description">{ticketDetail(selectedTicket)} <span>·</span> {selectedTicket.requester}</p>
              <div className="ticket-facts">
                <div className="ticket-fact"><span>Requester</span><b>{selectedTicket.requester}</b></div>
                <div className="ticket-fact"><span>Opened</span><b>{selectedTicket.created_at?.slice(0, 10) ?? '—'}</b></div>
                <div className="ticket-fact"><span>Record status</span><b>{selectedTicket.database_status}</b></div>
              </div>

              <div className="run-card">
                <div className="run-card-head">
                  <div className="run-icon"><Sparkles size={18} /></div>
                  <div><div className="run-title">Agent desk</div><div className="run-subtitle">Boss coordinates · specialists join only as needed</div></div>
                  <button className="run-button" type="button" onClick={() => void startRun()} disabled={runState === 'running' || !selectedTicket}>
                    {runState === 'running' ? <><LoaderCircle className="spin" size={16} /> Running</> : <><Play size={15} fill="currentColor" /> Start team</>}
                  </button>
                </div>
                <div className="agent-roster">
                  {AGENTS.map((agent) => {
                    const working = activeAgent === agent.name
                    const participated = involvedAgents.has(agent.name)
                    const done = runState === 'complete' && participated
                    return (
                      <div className={`agent-chip ${working ? 'agent-chip-working' : ''}`} key={agent.name}>
                        <span className={`agent-monogram ${agent.color}`}>{working ? <LoaderCircle size={14} className="spin" /> : done ? <Check size={14} /> : agent.mark}</span>
                        <span className="agent-chip-copy"><b>{agent.name}</b><small>{working ? 'Working now' : done ? 'Contributed' : agent.title}</small></span>
                        <span className={`agent-indicator ${working ? 'agent-indicator-active' : done ? 'agent-indicator-done' : ''}`} />
                      </div>
                    )
                  })}
                </div>

                <div className="live-section-head"><span>{runState === 'running' ? 'Live activity' : runState === 'complete' ? 'Run summary' : 'Run activity'}</span><span className="live-label">{runState === 'running' ? <><i /> LIVE</> : runState === 'complete' ? 'COMPLETE' : 'READY'}</span></div>
                {runState === 'idle' && <div className="activity-placeholder"><Clock3 size={16} /><span>Start the team to see real MCP calls and agent handoffs here.</span></div>}
                {runState === 'running' && !runEvents.length && <div className="activity-placeholder"><LoaderCircle size={16} className="spin" /><span>Waiting for the first audit event…</span></div>}
                {!!runEvents.length && <div className="activity-feed">
                  {[...runEvents].slice(-7).reverse().map((event, index) => (
                    <div className="activity-entry" key={`${event.run_id}-${event.timestamp}-${index}`}>
                      <span className={`activity-avatar ${agentColor(event.details?.target_agent ?? event.actor)}`}>{String(event.details?.target_agent ?? event.actor ?? '?').slice(0, 1)}</span>
                      <div className="activity-entry-body"><div><b>{event.details?.target_agent ?? event.actor ?? 'Team'}</b><span>{eventCopy(event)}</span></div>
                        {event.event === 'mcp_tool.started' && <code>{event.details?.tool_name}</code>}
                        {event.event === 'agent.delegation.completed' && <p className="activity-quote">{String(event.details?.response ?? '').slice(0, 220)}</p>}
                        {event.event === 'agent.run.completed' && <p className="activity-quote">{String(event.details?.response ?? '').slice(0, 260)}</p>}
                      </div>
                      <time>{event.timestamp ? new Date(event.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}</time>
                    </div>
                  ))}
                </div>}
                {runState === 'error' && <div className="error-banner run-error" role="alert">{runError}</div>}
                {runResult && <div className="final-response"><div className="final-response-title"><CheckCircle2 size={15} /> Boss’s recommendation</div><p>{runResult.response}</p></div>}
              </div>

              {approvalMentioned && <form className="approval-card" onSubmit={(event) => void approveTransaction(event)}>
                <div className="approval-card-heading"><div className="approval-icon"><ShieldCheck size={19} /></div><div><div className="approval-title">Human approval requested</div><div className="approval-caption">Review details, then confirm explicitly.</div></div><span className="approval-review-tag">REVIEW</span></div>
                <div className="approval-grid">
                  <label>Action type<select value={approvalKind} onChange={(event) => setApprovalKind(event.target.value as ApprovalKind)}><option value="invoice">Invoice payment</option><option value="rent">Rent payment</option><option value="purchase">Purchase</option></select></label>
                  {approvalKind === 'purchase' ? <>
                    <label>Vendor<select required value={purchaseVendor} onChange={(event) => setPurchaseVendor(event.target.value)}><option value="">Choose vendor</option>{(context?.vendors ?? []).map((vendor) => <option key={vendor.id} value={vendor.id}>{vendor.name} · #{vendor.id}</option>)}</select></label>
                    <label>Amount<input required type="number" min="0.01" step="0.01" value={purchaseAmount} onChange={(event) => setPurchaseAmount(event.target.value)} placeholder="0.00" /></label>
                  </> : <>
                    <label>Reference<input readOnly value={approvalKind === 'invoice' ? selectedInvoice?.id ?? '' : selectedLease?.id ?? ''} /></label>
                    <label>Amount<input readOnly value={approvalKind === 'invoice' ? selectedInvoice?.amount ?? '' : selectedLease?.monthly_rent ?? ''} /></label>
                  </>}
                  <label>Approver name<input required value={approver} onChange={(event) => setApprover(event.target.value)} placeholder="Your name" maxLength={120} /></label>
                </div>
                <label className="approval-confirm"><input type="checkbox" checked={humanApproved} onChange={(event) => setHumanApproved(event.target.checked)} /><span>I approve this {approvalKind === 'purchase' ? 'purchase' : 'payment'}.</span></label>
                <div className="approval-actions"><span>Checking: ${checkingBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span><button type="submit" disabled={!humanApproved || !approver.trim() || approvalBusy || (approvalKind === 'purchase' && (!purchaseVendor || !purchaseAmount))}>{approvalBusy ? <LoaderCircle size={15} className="spin" /> : <Check size={15} />}Approve {approvalKind === 'purchase' ? 'purchase' : 'payment'}</button></div>
                {approvalMessage && <p className="approval-message" role="status">{approvalMessage}</p>}
              </form>}
            </> : <div className="ticket-work-empty">Select a ticket to begin.</div>}
          </section>

          <aside className="inspector-column">
            <section className="cash-panel">
              <div className="cash-panel-top"><span className="cash-icon"><Wallet size={17} /></span><span className="cash-account-label">Checking account</span><span className="cash-live"><i /> LIVE</span></div>
              <div className="cash-amount">${checkingBalance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
              <div className="cash-date">As of {checkingDate}</div>
              <div className="cash-meter"><span style={{ width: meterWidth }} /></div>
              <div className="cash-foot"><span>Current balance</span><span>Human-approved only</span></div>
            </section>

            <section className="side-panel ticket-context">
              <div className="side-panel-title"><span>Ticket snapshot</span><FileText size={15} /></div>
              {selectedTicket ? <>
                <div className="context-subject">{ticketHeading(selectedTicket)}</div>
                <div className="context-row"><span>Requester</span><b>{selectedTicket.requester}</b></div>
                {selectedTicket.sku && <div className="context-row"><span>SKU</span><b className="mono">{selectedTicket.sku}</b></div>}
                {selectedTicket.qty != null && <div className="context-row"><span>Quantity</span><b>{selectedTicket.qty}{selectedTicket.size ? ` · size ${selectedTicket.size}` : ''}</b></div>}
                {selectedInvoice && <div className="context-alert"><CreditCard size={14} /><span>Invoice #{selectedInvoice.id} · ${Number(selectedInvoice.amount).toFixed(2)} · {selectedInvoice.status}</span></div>}
                {selectedLease && <div className="context-alert context-alert-blue"><Landmark size={14} /><span>Lease #{selectedLease.id} · ${Number(selectedLease.monthly_rent).toLocaleString()} rent</span></div>}
                {selectedTicket.id === 103 && <div className="context-alert context-alert-gold"><PackageCheck size={14} /><span>{Math.max(0, Number(selectedTicket.qty ?? 0) - Number(selectedTicket.details?.inventory?.find((item: { size: string }) => item.size === selectedTicket.size)?.qty ?? 0))} more size-{selectedTicket.size} units requested than currently on hand</span></div>}
              </> : <p className="context-empty">Waiting for ticket data.</p>}
            </section>

            <section className="side-panel tools-panel">
              <div className="side-panel-title"><span>Tools used</span><Activity size={15} /></div>
              {usedTools.length ? <ul className="used-tool-list">{usedTools.map((tool) => <li key={tool}><CheckCircle2 size={13} /><code>{tool}</code></li>)}</ul> : <p className="context-empty">No tools called in this session.</p>}
            </section>

            <section className="guardrail-note"><ShieldCheck size={17} /><div><b>Human in the loop</b><p>No emails are sent and no cash moves until you explicitly approve.</p></div></section>
            {approvalMessage && !approvalMentioned && <div className="side-feedback" role="status">{approvalMessage}</div>}
          </aside>
        </div>
        <footer className="page-footer"><span><span className="footer-dot" /> Local desk · connected to Campus Customs API</span><span>Run history is recorded in the audit trail</span></footer>
      </main>
    </div>
  )
}

export default App
