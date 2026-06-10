import React, { useState, useEffect, useMemo } from 'react';
import {
  Bot, RefreshCw, Wrench, AlertCircle, User, Cpu,
  ChevronDown, ChevronRight, Search,
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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
      padding: '2px 7px', borderRadius: 4, fontSize: '0.67rem',
      fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em',
      whiteSpace: 'nowrap',
    }}>
      {m.label}
    </span>
  );
}

function fmtMs(ms) {
  if (!ms && ms !== 0) return '—';
  return ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(2)}s`;
}

function fmt(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-IN', {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  });
}

// ── Left panel: run card ──────────────────────────────────────────────────────

function RunCard({ run, selected, onClick }) {
  return (
    <div className={`lg-run-card${selected ? ' lg-run-card--selected' : ''}`} onClick={onClick}>
      <div className="lg-run-card-top">
        <span className="agent-name-badge">{run.agent_name}</span>
        <StatusBadge status={run.status} />
      </div>
      <div className="lg-run-card-model">{run.model}</div>
      {run.query && (
        <div className="lg-run-card-query">
          {run.query.length > 70 ? run.query.slice(0, 70) + '…' : run.query}
        </div>
      )}
      <div className="lg-run-card-stats">
        <span>{fmtMs(run.latency_ms)}</span>
        <span className="lg-dot">·</span>
        <span>
          <span style={{ color: '#60a5fa' }}>{run.tokens_in}↑</span>
          {' '}
          <span style={{ color: '#4ade80' }}>{run.tokens_out}↓</span>
        </span>
        <span className="lg-dot">·</span>
        <span>₹{(run.cost_inr || 0).toFixed(4)}</span>
      </div>
      <div className="lg-run-card-time">{fmt(run.started_at)}</div>
    </div>
  );
}

// ── Output trace: individual message bubbles ──────────────────────────────────

function ToolCallCard({ tc }) {
  const [open, setOpen] = useState(false);
  let args = {};
  try { args = JSON.parse(tc.function.arguments); } catch { args = tc.function.arguments; }

  return (
    <div className="lg-tool-call-card" onClick={() => setOpen(o => !o)}>
      <div className="lg-tool-call-header">
        <Wrench size={11} style={{ color: '#a78bfa' }} />
        <span className="lg-tool-call-name">{tc.function.name}</span>
        <span style={{ marginLeft: 'auto', color: 'var(--text-muted)' }}>
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </span>
      </div>
      {open && (
        <pre className="lg-tool-call-args">
          {typeof args === 'object' ? JSON.stringify(args, null, 2) : String(args)}
        </pre>
      )}
    </div>
  );
}

function MessageBubble({ msg }) {
  if (msg.role === 'user') {
    return (
      <div className="lg-msg lg-msg--user">
        <div className="lg-msg-icon lg-msg-icon--user"><User size={12} /></div>
        <div className="lg-msg-body">
          <div className="lg-msg-role">User</div>
          <div className="lg-msg-text">{msg.content}</div>
        </div>
      </div>
    );
  }

  if (msg.role === 'assistant') {
    const hasCalls = msg.tool_calls?.length > 0;
    const hasText  = msg.content && msg.content.trim();
    return (
      <div className="lg-msg lg-msg--ai">
        <div className="lg-msg-icon lg-msg-icon--ai"><Cpu size={12} /></div>
        <div className="lg-msg-body">
          <div className="lg-msg-role">AI</div>
          {hasCalls && (
            <div className="lg-tool-calls-list">
              {msg.tool_calls.map((tc, i) => <ToolCallCard key={i} tc={tc} />)}
            </div>
          )}
          {hasText && <div className="lg-msg-text">{msg.content}</div>}
        </div>
      </div>
    );
  }

  if (msg.role === 'tool') {
    return (
      <div className="lg-msg lg-msg--tool">
        <div className="lg-msg-icon lg-msg-icon--tool"><Wrench size={11} /></div>
        <div className="lg-msg-body">
          <div className="lg-msg-role">
            <span style={{ color: '#a78bfa' }}>{msg.name}</span>
            <span style={{ color: 'var(--text-muted)' }}> result</span>
          </div>
          <div className="lg-msg-text lg-msg-text--tool">{msg.content}</div>
        </div>
      </div>
    );
  }

  return null;
}

// ── Right panel: detail view ──────────────────────────────────────────────────

function RunDetail({ run }) {
  const [tab, setTab] = useState('output');

  const messages = useMemo(() => {
    if (!run.messages?.length) return [];
    return run.messages;
  }, [run.run_id]);

  const toolsDefined = run.tools_defined || [];
  const toolsCalled  = run.tools_called  || [];

  return (
    <div className="lg-detail">
      {/* Header */}
      <div className="lg-detail-header">
        <div className="lg-detail-header-left">
          <span className="lg-detail-agent">{run.agent_name}</span>
          <span className="lg-detail-model-badge">{run.model}</span>
          <StatusBadge status={run.status} />
        </div>
        <div className="lg-detail-header-stats">
          <span className="lg-hstat">
            <span className="lg-hstat-label">latency</span>
            {fmtMs(run.latency_ms)}
          </span>
          <span className="lg-hstat-sep" />
          <span className="lg-hstat">
            <span className="lg-hstat-label">tokens</span>
            <span style={{ color: '#60a5fa' }}>{run.tokens_in.toLocaleString()}↑</span>
            {' / '}
            <span style={{ color: '#4ade80' }}>{run.tokens_out.toLocaleString()}↓</span>
          </span>
          <span className="lg-hstat-sep" />
          <span className="lg-hstat">
            <span className="lg-hstat-label">cost</span>
            ₹{(run.cost_inr || 0).toFixed(4)}
            <span style={{ color: 'var(--text-muted)', marginLeft: 4 }}>
              ${(run.cost_usd || 0).toFixed(6)}
            </span>
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="lg-tabs">
        {[
          { id: 'input',  label: 'Input'  },
          { id: 'output', label: 'Output' },
          { id: 'tools',  label: 'Tools', count: toolsCalled.length },
        ].map(({ id, label, count }) => (
          <button
            key={id}
            className={`lg-tab${tab === id ? ' lg-tab--active' : ''}`}
            onClick={() => setTab(id)}
          >
            {label}
            {count > 0 && <span className="lg-tab-count">{count}</span>}
          </button>
        ))}
      </div>

      {/* Body */}
      <div className="lg-detail-body">

        {/* INPUT TAB */}
        {tab === 'input' && (
          <div className="lg-input-section">
            <div className="lg-section-label">Query</div>
            <div className="lg-input-text">{run.query || '—'}</div>
            <div className="lg-token-row">
              <div className="lg-token-card">
                <div className="lg-token-label">Input tokens</div>
                <div className="lg-token-value" style={{ color: '#60a5fa' }}>
                  {run.tokens_in.toLocaleString()}
                </div>
              </div>
              <div className="lg-token-card">
                <div className="lg-token-label">Output tokens</div>
                <div className="lg-token-value" style={{ color: '#4ade80' }}>
                  {run.tokens_out.toLocaleString()}
                </div>
              </div>
              <div className="lg-token-card">
                <div className="lg-token-label">Total tokens</div>
                <div className="lg-token-value">
                  {(run.tokens_in + run.tokens_out).toLocaleString()}
                </div>
              </div>
              <div className="lg-token-card">
                <div className="lg-token-label">Started</div>
                <div className="lg-token-value" style={{ fontSize: '0.82rem' }}>
                  {fmt(run.started_at)}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* OUTPUT TAB */}
        {tab === 'output' && (
          <div className="lg-trace">
            {run.error && (
              <div className="lg-error-banner">
                <AlertCircle size={13} style={{ flexShrink: 0 }} />
                {run.error}
              </div>
            )}
            {messages.length > 0
              ? messages.map((msg, i) => <MessageBubble key={i} msg={msg} />)
              : (
                <>
                  {run.query   && <MessageBubble msg={{ role: 'user',      content: run.query    }} />}
                  {run.response && <MessageBubble msg={{ role: 'assistant', content: run.response }} />}
                </>
              )
            }
          </div>
        )}

        {/* TOOLS TAB */}
        {tab === 'tools' && (
          <div className="lg-tools-section">
            {toolsDefined.length > 0 && (
              <div className="lg-tools-group">
                <div className="lg-section-label">Available ({toolsDefined.length})</div>
                <div className="lg-tools-grid">
                  {toolsDefined.map((t, i) => {
                    const name = t?.function?.name || t?.name || `tool_${i}`;
                    const desc = t?.function?.description || t?.description || '';
                    return (
                      <div key={i} className="lg-tool-def-card">
                        <div className="lg-tool-def-name">
                          <Wrench size={11} style={{ color: '#a78bfa' }} /> {name}
                        </div>
                        {desc && <div className="lg-tool-def-desc">{desc}</div>}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {toolsCalled.length > 0 && (
              <div className="lg-tools-group">
                <div className="lg-section-label">Invoked in order ({toolsCalled.length})</div>
                {toolsCalled.map((t, i) => {
                  let args = {};
                  try { args = JSON.parse(t.input); } catch { args = t.input; }
                  return (
                    <div key={i} className="lg-tool-invoked-card">
                      <div className="lg-tool-invoked-header">
                        <span className="lg-tool-step">{i + 1}</span>
                        <Wrench size={11} style={{ color: '#a78bfa' }} />
                        <span className="lg-tool-invoked-name">{t.name}</span>
                      </div>
                      <pre className="agent-tool-input">
                        {typeof args === 'object' ? JSON.stringify(args, null, 2) : String(args)}
                      </pre>
                    </div>
                  );
                })}
              </div>
            )}

            {toolsDefined.length === 0 && toolsCalled.length === 0 && (
              <div style={{ color: 'var(--text-muted)', padding: '2rem', textAlign: 'center', fontSize: '0.85rem' }}>
                No tools were used in this run.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Page root ─────────────────────────────────────────────────────────────────

export default function AgentRunsPage({ getToken }) {
  const authHeaders = async () => {
    const token = await getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const [runs, setRuns]           = useState([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
  const [search, setSearch]       = useState('');
  const [filterModel, setModel]   = useState('all');
  const [filterStatus, setStatus] = useState('all');
  const [selectedId, setSelectedId] = useState(null);

  const fetchRuns = async () => {
    setLoading(true); setError('');
    try {
      const res = await fetch(`${API_BASE_URL}/v1/agent/runs`, { headers: await authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setRuns(data);
      if (data.length > 0 && !selectedId) setSelectedId(data[0].run_id);
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

  const selectedRun = filtered.find(r => r.run_id === selectedId) || filtered[0] || null;

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

      <div className="lg-layout">
        {/* ── Left panel ── */}
        <div className="lg-left">
          <div className="lg-filter-bar">
            <div className="lg-search-wrap">
              <Search size={13} className="lg-search-icon" />
              <input
                className="lg-search"
                placeholder="Search…"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
            <div style={{ display: 'flex', gap: '0.4rem' }}>
              <select className="agent-filter-select" style={{ flex: 1, fontSize: '0.78rem' }} value={filterModel} onChange={e => setModel(e.target.value)}>
                <option value="all">All models</option>
                {allModels.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
              <select className="agent-filter-select" style={{ flex: 1, fontSize: '0.78rem' }} value={filterStatus} onChange={e => setStatus(e.target.value)}>
                <option value="all">All status</option>
                <option value="completed">Completed</option>
                <option value="tool_pending">Tool Pending</option>
                <option value="error">Error</option>
              </select>
            </div>
          </div>

          {error && (
            <div className="auth-error" style={{ margin: '0 0 0.75rem', fontSize: '0.8rem' }}>{error}</div>
          )}

          {loading ? (
            <div style={{ color: 'var(--text-muted)', padding: '2rem', textAlign: 'center', fontSize: '0.85rem' }}>
              Loading…
            </div>
          ) : filtered.length === 0 ? (
            <div className="agent-empty-state">
              <Bot size={34} style={{ color: 'var(--text-muted)', marginBottom: '0.75rem' }} />
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                {runs.length === 0 ? 'No runs yet.' : 'No matches.'}
              </p>
            </div>
          ) : (
            <div className="lg-run-list">
              {filtered.map(run => (
                <RunCard
                  key={run.run_id}
                  run={run}
                  selected={selectedRun?.run_id === run.run_id}
                  onClick={() => setSelectedId(run.run_id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* ── Right panel ── */}
        <div className="lg-right">
          {selectedRun
            ? <RunDetail run={selectedRun} />
            : (
              <div className="lg-empty-detail">
                <Bot size={38} style={{ color: 'var(--text-muted)', marginBottom: '0.75rem' }} />
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Select a run to inspect</p>
              </div>
            )
          }
        </div>
      </div>
    </main>
  );
}
