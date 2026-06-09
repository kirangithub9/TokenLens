import React, { useState, useEffect, useMemo } from 'react';
import {
  Bot, Zap, DollarSign, Hash, RefreshCw,
  ChevronDown, ChevronRight, Wrench, AlertCircle, CheckCircle, Clock,
} from 'lucide-react';
import { auth } from './firebase';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function authHeaders() {
  const user = auth.currentUser ?? await new Promise(resolve => {
    const unsub = auth.onAuthStateChanged(u => { unsub(); resolve(u); });
  });
  if (!user) return {};
  const token = await user.getIdToken();
  return { Authorization: `Bearer ${token}` };
}

const STATUS_META = {
  completed:    { label: 'Completed',    color: '#4ade80', bg: 'rgba(34,197,94,0.12)',   border: 'rgba(34,197,94,0.25)'   },
  tool_pending: { label: 'Tool Pending', color: '#fb923c', bg: 'rgba(251,146,60,0.12)',  border: 'rgba(251,146,60,0.25)'  },
  running:      { label: 'Running',      color: '#60a5fa', bg: 'rgba(96,165,250,0.12)',  border: 'rgba(96,165,250,0.25)'  },
  error:        { label: 'Error',        color: '#f87171', bg: 'rgba(248,113,113,0.12)', border: 'rgba(248,113,113,0.25)' },
};

function StatusBadge({ status }) {
  const m = STATUS_META[status] || STATUS_META.running;
  return (
    <span style={{
      background: m.bg, color: m.color, border: `1px solid ${m.border}`,
      padding: '2px 8px', borderRadius: '4px', fontSize: '0.7rem',
      fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em',
      whiteSpace: 'nowrap',
    }}>
      {m.label}
    </span>
  );
}

function fmt(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-IN', {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  });
}

function fmtMs(ms) {
  if (!ms && ms !== 0) return '—';
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(2)} s`;
}

function ToolChip({ name }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      background: 'rgba(124,109,240,0.1)', border: '1px solid rgba(124,109,240,0.25)',
      color: 'var(--accent-hover)', borderRadius: 4, padding: '2px 8px',
      fontSize: '0.75rem', fontFamily: 'monospace', fontWeight: 500,
    }}>
      <Wrench size={11} />
      {name}
    </span>
  );
}

function RunRow({ run }) {
  const [open, setOpen] = useState(false);
  const toolsCalled  = run.tools_called  || [];
  const toolsDefined = run.tools_defined || [];

  let parsedInput = null;
  try { parsedInput = toolsCalled.map(t => ({ ...t, inputParsed: JSON.parse(t.input) })); }
  catch { parsedInput = toolsCalled; }

  return (
    <>
      <tr
        className="agent-run-row"
        onClick={() => setOpen(o => !o)}
      >
        <td className="agent-td-expand">
          {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        </td>
        <td className="agent-td">
          <span className="agent-name-badge">{run.agent_name}</span>
        </td>
        <td className="agent-td agent-td-mono">{run.model}</td>
        <td className="agent-td agent-td-query">
          {run.query ? run.query.slice(0, 80) + (run.query.length > 80 ? '…' : '') : <span style={{ color: 'var(--text-muted)' }}>—</span>}
        </td>
        <td className="agent-td"><StatusBadge status={run.status} /></td>
        <td className="agent-td agent-td-mono">
          {(run.tokens_in + run.tokens_out).toLocaleString()}
          <span className="agent-td-sub">&nbsp;({run.tokens_in}↑ {run.tokens_out}↓)</span>
        </td>
        <td className="agent-td agent-td-mono">
          ₹{(run.cost_inr || 0).toFixed(4)}
          <span className="agent-td-sub">&nbsp;${(run.cost_usd || 0).toFixed(6)}</span>
        </td>
        <td className="agent-td agent-td-mono">{fmtMs(run.latency_ms)}</td>
        <td className="agent-td agent-td-dim">{fmt(run.started_at)}</td>
      </tr>

      {open && (
        <tr>
          <td colSpan={9} style={{ padding: 0 }}>
            <div className="agent-run-detail">

              <div className="agent-detail-grid">
                {/* Query */}
                <div className="agent-detail-block">
                  <div className="agent-detail-label">Input</div>
                  <div className="agent-detail-text">{run.query || '—'}</div>
                </div>

                {/* Response */}
                {run.response && (
                  <div className="agent-detail-block">
                    <div className="agent-detail-label">Output</div>
                    <div className="agent-detail-text">{run.response}</div>
                  </div>
                )}

                {/* Error */}
                {run.error && (
                  <div className="agent-detail-block agent-detail-error">
                    <div className="agent-detail-label" style={{ color: '#f87171' }}>
                      <AlertCircle size={13} style={{ verticalAlign: -2 }} /> Error
                    </div>
                    <div className="agent-detail-text">{run.error}</div>
                  </div>
                )}
              </div>

              <div className="agent-detail-row">
                {/* Tools defined */}
                {toolsDefined.length > 0 && (
                  <div className="agent-detail-section">
                    <div className="agent-detail-label">Tools available ({toolsDefined.length})</div>
                    <div className="agent-tool-chips">
                      {toolsDefined.map((t, i) => (
                        <ToolChip key={i} name={t?.function?.name || t?.name || String(i)} />
                      ))}
                    </div>
                  </div>
                )}

                {/* Tools called */}
                {toolsCalled.length > 0 && (
                  <div className="agent-detail-section">
                    <div className="agent-detail-label">Tools invoked ({toolsCalled.length})</div>
                    {(parsedInput || toolsCalled).map((t, i) => (
                      <div key={i} className="agent-tool-call-card">
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                          <Wrench size={12} style={{ color: 'var(--accent)' }} />
                          <span style={{ fontFamily: 'monospace', fontWeight: 600, fontSize: '0.82rem' }}>
                            {t.name}
                          </span>
                        </div>
                        <pre className="agent-tool-input">
                          {typeof t.inputParsed === 'object'
                            ? JSON.stringify(t.inputParsed, null, 2)
                            : t.input}
                        </pre>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Meta row */}
              <div className="agent-detail-meta">
                <span>Run ID: <code>{run.run_id}</code></span>
                {run.finished_at && <span>Finished: {fmt(run.finished_at)}</span>}
                <span>Latency: {fmtMs(run.latency_ms)}</span>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function SummaryCard({ icon: Icon, label, value, sub, gradient }) {
  return (
    <div className="metric-card">
      <div className="metric-card-icon" style={{ background: gradient }}>
        <Icon size={18} />
      </div>
      <div className="metric-card-body">
        <p className="metric-card-label">{label}</p>
        <p className="metric-card-value">{value}</p>
        {sub && <p className="metric-card-sub">{sub}</p>}
      </div>
    </div>
  );
}

export default function AgentRunsPage() {
  const [runs, setRuns]         = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');
  const [search, setSearch]     = useState('');
  const [filterModel, setModel] = useState('all');
  const [filterStatus, setStatus] = useState('all');

  const fetchRuns = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE_URL}/v1/agent/runs`, {
        headers: await authHeaders(),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setRuns(await res.json());
    } catch (e) {
      setError(`Could not load runs: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchRuns(); }, []);

  const allModels = useMemo(() => [...new Set(runs.map(r => r.model))], [runs]);

  const filtered = useMemo(() => runs.filter(r => {
    if (filterStatus !== 'all' && r.status !== filterStatus) return false;
    if (filterModel  !== 'all' && r.model  !== filterModel)  return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        r.agent_name?.toLowerCase().includes(q) ||
        r.query?.toLowerCase().includes(q) ||
        r.model?.toLowerCase().includes(q)
      );
    }
    return true;
  }), [runs, filterStatus, filterModel, search]);

  const stats = useMemo(() => {
    const total    = runs.length;
    const cost_inr = runs.reduce((s, r) => s + (r.cost_inr || 0), 0);
    const tokens   = runs.reduce((s, r) => s + r.tokens_in + r.tokens_out, 0);
    const lats     = runs.filter(r => r.latency_ms).map(r => r.latency_ms);
    const avg_lat  = lats.length ? lats.reduce((a, b) => a + b, 0) / lats.length : 0;
    return { total, cost_inr, tokens, avg_lat };
  }, [runs]);

  return (
    <main className="metrics-main">
      <header className="metrics-header">
        <div className="metrics-header-title">
          <div className="header-title-icon"><Bot size={16} /></div>
          <h1>AGENT RUNS</h1>
        </div>
        <button className="agent-refresh-btn" onClick={fetchRuns} title="Refresh">
          <RefreshCw size={14} />
        </button>
      </header>

      <div className="metrics-body">
        {/* Summary cards */}
        <div className="metric-cards-grid" style={{ marginBottom: '1.5rem' }}>
          <SummaryCard
            icon={Bot} label="Total Runs" value={stats.total}
            sub={`${filtered.length} shown`}
            gradient="linear-gradient(135deg,#7c6df0,#c084fc)"
          />
          <SummaryCard
            icon={DollarSign} label="Total Cost"
            value={`₹${stats.cost_inr.toFixed(4)}`}
            sub={`$${runs.reduce((s, r) => s + (r.cost_usd || 0), 0).toFixed(6)}`}
            gradient="linear-gradient(135deg,#10b981,#34d399)"
          />
          <SummaryCard
            icon={Hash} label="Total Tokens"
            value={stats.tokens >= 1000 ? `${(stats.tokens / 1000).toFixed(1)}k` : stats.tokens}
            sub={`across ${stats.total} runs`}
            gradient="linear-gradient(135deg,#f59e0b,#fcd34d)"
          />
          <SummaryCard
            icon={Zap} label="Avg Latency"
            value={fmtMs(stats.avg_lat)}
            sub="per LLM call"
            gradient="linear-gradient(135deg,#3b82f6,#93c5fd)"
          />
        </div>

        {/* Filters */}
        <div className="agent-filter-bar">
          <input
            className="agent-search"
            placeholder="Search by agent name, query, or model…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <select className="agent-filter-select" value={filterModel} onChange={e => setModel(e.target.value)}>
            <option value="all">All models</option>
            {allModels.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
          <select className="agent-filter-select" value={filterStatus} onChange={e => setStatus(e.target.value)}>
            <option value="all">All statuses</option>
            <option value="completed">Completed</option>
            <option value="tool_pending">Tool Pending</option>
            <option value="error">Error</option>
          </select>
        </div>

        {/* Error */}
        {error && (
          <div className="auth-error" style={{ marginBottom: '1rem' }}>{error}</div>
        )}

        {/* Table */}
        {loading ? (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '3rem' }}>
            Loading runs…
          </div>
        ) : filtered.length === 0 ? (
          <div className="agent-empty-state">
            <Bot size={40} style={{ color: 'var(--text-muted)', marginBottom: '1rem' }} />
            <p style={{ color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
              {runs.length === 0 ? 'No agent runs yet.' : 'No runs match your filters.'}
            </p>
            {runs.length === 0 && (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                Use your API key with <code style={{ background: 'var(--glass)', padding: '1px 6px', borderRadius: 3 }}>POST /v1/agent/run</code> to start tracking.
              </p>
            )}
          </div>
        ) : (
          <div className="agent-table-wrap">
            <table className="agent-runs-table">
              <thead>
                <tr>
                  <th style={{ width: 28 }} />
                  <th>Agent</th>
                  <th>Model</th>
                  <th>Query</th>
                  <th>Status</th>
                  <th>Tokens</th>
                  <th>Cost</th>
                  <th>Latency</th>
                  <th>Started</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(run => <RunRow key={run.run_id} run={run} />)}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
