import React, { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Cell, LabelList,
  ResponsiveContainer, CartesianGrid,
} from 'recharts';
import { Users, Zap, DollarSign, Activity, ChevronDown, ChevronUp, RefreshCw } from 'lucide-react';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const MODEL_COLORS = {
  gemma:      '#7c6df0',
  gpt4:       '#10b981',
  'gpt4o-mini': '#f59e0b',
  openai:     '#3b82f6',
};
const DEFAULT_COLOR = '#9ca3af';

const MODEL_LABELS = {
  gemma:      'Gemma',
  gpt4:       'GPT-4o Mini',
  'gpt4o-mini': 'GPT-4o Mini',
  openai:     'OpenAI',
};

function fmt(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}k`;
  return String(Math.round(n ?? 0));
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function StatChip({ label, value, sub }) {
  return (
    <div className="admin-stat-chip">
      <span className="admin-stat-val">{value}</span>
      {sub && <span className="admin-stat-sub">{sub}</span>}
      <span className="admin-stat-label">{label}</span>
    </div>
  );
}

function ModelBarChart({ models }) {
  if (!models?.length) return <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>No model data</p>;

  const data = models.map(m => ({
    name:     MODEL_LABELS[m.model] || m.model,
    key:      m.model,
    tokens:   m.total_tokens,
    requests: m.requests,
  }));

  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} margin={{ top: 24, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
        <XAxis dataKey="name" tick={{ fill: 'var(--text-dim)', fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={fmt} width={36} />
        <Tooltip
          contentStyle={{ background: '#1a1a1e', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, fontSize: '0.8rem' }}
          formatter={(val, name) => [fmt(val), name === 'tokens' ? 'Tokens' : 'Requests']}
        />
        <Bar dataKey="tokens" radius={[4, 4, 0, 0]}>
          {data.map(d => (
            <Cell key={d.key} fill={MODEL_COLORS[d.key] || DEFAULT_COLOR} />
          ))}
          <LabelList dataKey="name" position="top" style={{ fill: 'var(--text-dim)', fontSize: 10, fontWeight: 600 }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function QueryHistory({ userId }) {
  const [history, setHistory]   = useState(null);
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const h = await authHeaders();
        const res = await fetch(`${API_BASE_URL}/analytics/user/${userId}/history?page_size=10`, { headers: h });
        if (res.ok) setHistory(await res.json());
      } finally {
        setLoading(false);
      }
    })();
  }, [userId]);

  if (loading) return <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '0.5rem 0' }}>Loading history…</p>;
  if (!history?.results?.length) return <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '0.5rem 0' }}>No queries yet.</p>;

  return (
    <div className="admin-history-table-wrap">
      <table className="admin-history-table">
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Model</th>
            <th>Query</th>
            <th>Tokens In</th>
            <th>Tokens Out</th>
            <th>Cost USD</th>
            <th>Cost INR</th>
          </tr>
        </thead>
        <tbody>
          {history.results.map(row => (
            <tr key={row.id}>
              <td style={{ whiteSpace: 'nowrap' }}>{fmtDate(row.created_at)}</td>
              <td>
                <span className="admin-model-tag" style={{ background: MODEL_COLORS[row.model_used] || DEFAULT_COLOR }}>
                  {MODEL_LABELS[row.model_used] || row.model_used}
                </span>
              </td>
              <td className="admin-query-text">{row.query_preview || '—'}</td>
              <td>{fmt(row.input_tokens)}</td>
              <td>{fmt(row.output_tokens)}</td>
              <td>${row.cost_usd?.toFixed(6)}</td>
              <td>₹{row.cost_inr?.toFixed(4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function UserCard({ user }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={`admin-user-card ${expanded ? 'expanded' : ''}`}>
      {/* Header row — always visible */}
      <div className="admin-user-header" onClick={() => setExpanded(e => !e)}>
        <div className="admin-user-identity">
          <div className="admin-avatar">{(user.display_name?.[0] ?? 'U').toUpperCase()}</div>
          <div>
            <div className="admin-user-name">{user.display_name}</div>
            <div className="admin-user-id">{user.user_id}</div>
          </div>
        </div>
        <div className="admin-user-summary">
          <span>{fmt(user.total_requests)} queries</span>
          <span>{fmt(user.total_tokens_in + user.total_tokens_out)} tokens</span>
          <span>${user.total_cost_usd?.toFixed(4)}</span>
          <span>₹{user.total_cost_inr?.toFixed(2)}</span>
          <span className="admin-last-seen">{fmtDate(user.last_seen)}</span>
        </div>
        {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="admin-user-detail">
          <div className="admin-detail-grid">
            {/* Stat chips */}
            <div className="admin-stat-chips">
              <StatChip label="Queries"    value={fmt(user.total_requests)} />
              <StatChip label="Tokens In"  value={fmt(user.total_tokens_in)} />
              <StatChip label="Tokens Out" value={fmt(user.total_tokens_out)} />
              <StatChip label="Cost"       value={`$${user.total_cost_usd?.toFixed(6)}`} sub={`₹${user.total_cost_inr?.toFixed(4)}`} />
            </div>

            {/* Model bar chart */}
            <div className="admin-chart-section">
              <h4 className="admin-section-title">Model Usage</h4>
              <ModelBarChart models={user.models} />
            </div>
          </div>

          {/* Query history */}
          <div style={{ marginTop: '1.25rem' }}>
            <h4 className="admin-section-title">Recent Queries</h4>
            <QueryHistory userId={user.user_id} />
          </div>
        </div>
      )}
    </div>
  );
}

export default function AdminPage({ getToken }) {
  const authHeaders = async () => {
    const token = await getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  };
  const [users, setUsers]     = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const h = await authHeaders();
      const res = await fetch(`${API_BASE_URL}/analytics/users`, { headers: h });
      if (!res.ok) throw new Error('Failed to load users');
      setUsers(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const totalQueries = users.reduce((s, u) => s + u.total_requests, 0);
  const totalTokens  = users.reduce((s, u) => s + u.total_tokens_in + u.total_tokens_out, 0);
  const totalUsd     = users.reduce((s, u) => s + u.total_cost_usd, 0);
  const totalInr     = users.reduce((s, u) => s + u.total_cost_inr, 0);

  return (
    <main className="main-chat">
      <header className="chat-header">
        <div className="header-title">
          <div className="header-title-icon">A</div>
          <h1>ADMIN</h1>
        </div>
        <button className="theme-toggle-btn" onClick={load} title="Refresh">
          <RefreshCw size={16} />
        </button>
      </header>

      <div className="messages-container" style={{ padding: '1.5rem', overflowY: 'auto' }}>

        {/* Summary cards */}
        <div className="admin-summary-row">
          {[
            { icon: Users,      label: 'Total Users',   value: users.length },
            { icon: Activity,   label: 'Total Queries',  value: fmt(totalQueries) },
            { icon: Zap,        label: 'Total Tokens',   value: fmt(totalTokens) },
            { icon: DollarSign, label: 'Total Cost',     value: `$${totalUsd.toFixed(4)}`, sub: `₹${totalInr.toFixed(2)}` },
          ].map(({ icon: Icon, label, value, sub }) => (
            <div key={label} className="admin-summary-card">
              <div className="admin-summary-icon"><Icon size={18} /></div>
              <div>
                <div className="admin-summary-value">{value}{sub && <span className="admin-summary-sub"> / {sub}</span>}</div>
                <div className="admin-summary-label">{label}</div>
              </div>
            </div>
          ))}
        </div>

        {error && <div className="auth-error" style={{ margin: '1rem 0' }}>{error}</div>}

        {loading ? (
          <p style={{ color: 'var(--text-dim)', marginTop: '2rem', textAlign: 'center' }}>Loading users…</p>
        ) : users.length === 0 ? (
          <p style={{ color: 'var(--text-dim)', marginTop: '2rem', textAlign: 'center' }}>No users yet. Data appears after the first chat message.</p>
        ) : (
          <div className="admin-user-list">
            {users.map(u => <UserCard key={u.user_id} user={u} />)}
          </div>
        )}
      </div>
    </main>
  );
}
