import React, { useState, useEffect } from 'react';
import { Copy, RefreshCw, Trash2, Key, Check } from 'lucide-react';
import { auth } from './firebase';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function authHeaders() {
  const token = await auth.currentUser?.getIdToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function SettingsPage({ theme, setTheme }) {
  const [keyInfo, setKeyInfo]       = useState(null);   // { key_prefix, created_at, last_used }
  const [newKey, setNewKey]         = useState('');      // shown once after generation
  const [loading, setLoading]       = useState(true);
  const [copied, setCopied]         = useState(false);
  const [error, setError]           = useState('');

  useEffect(() => { fetchKeyInfo(); }, []);

  const fetchKeyInfo = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE_URL}/api-keys`, { headers: await authHeaders() });
      if (res.ok) setKeyInfo(await res.json());
      else setKeyInfo(null);
    } catch {
      setError('Could not reach the server.');
    } finally {
      setLoading(false);
    }
  };

  const generateKey = async () => {
    if (keyInfo && !window.confirm('This will revoke your existing key. Continue?')) return;
    setError('');
    try {
      const res = await fetch(`${API_BASE_URL}/api-keys`, {
        method: 'POST',
        headers: await authHeaders(),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to generate key.');
      setNewKey(data.key);
      await fetchKeyInfo();
    } catch (e) {
      setError(e.message);
    }
  };

  const revokeKey = async () => {
    if (!window.confirm('Revoke your API key? Any apps using it will stop working.')) return;
    setError('');
    try {
      await fetch(`${API_BASE_URL}/api-keys`, { method: 'DELETE', headers: await authHeaders() });
      setKeyInfo(null);
      setNewKey('');
    } catch {
      setError('Failed to revoke key.');
    }
  };

  const copyKey = () => {
    navigator.clipboard.writeText(newKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const fmt = (iso) => iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Never';

  return (
    <main className="main-chat">
      <header className="chat-header">
        <div className="header-title">
          <div className="header-title-icon">⚙</div>
          <h1>SETTINGS</h1>
        </div>
      </header>

      <div className="messages-container" style={{ padding: '2rem', maxWidth: '640px', margin: '0 auto', width: '100%' }}>

        {/* API Key section */}
        <div className="settings-section">
          <div className="settings-section-header">
            <Key size={18} />
            <h2>API Key</h2>
          </div>
          <p className="settings-description">
            Use your API key to call TokenLens models from your own code. Pass it as:<br />
            <code>Authorization: Bearer tl-...</code>
          </p>

          {error && <div className="auth-error" style={{ marginBottom: '1rem' }}>{error}</div>}

          {loading ? (
            <p style={{ color: 'var(--text-dim)' }}>Loading...</p>
          ) : (
            <>
              {/* Newly generated key — shown once */}
              {newKey && (
                <div className="api-key-reveal">
                  <p className="api-key-warning">⚠️ Copy this key now — it won't be shown again.</p>
                  <div className="api-key-box">
                    <code className="api-key-value">{newKey}</code>
                    <button className="api-key-copy-btn" onClick={copyKey}>
                      {copied ? <Check size={15} /> : <Copy size={15} />}
                      {copied ? 'Copied!' : 'Copy'}
                    </button>
                  </div>
                </div>
              )}

              {/* Existing key info */}
              {keyInfo && !newKey && (
                <div className="api-key-info">
                  <div className="api-key-row">
                    <span className="api-key-label">Key</span>
                    <span className="api-key-masked">{keyInfo.key_prefix}{'•'.repeat(20)}</span>
                  </div>
                  <div className="api-key-row">
                    <span className="api-key-label">Created</span>
                    <span>{fmt(keyInfo.created_at)}</span>
                  </div>
                  <div className="api-key-row">
                    <span className="api-key-label">Last used</span>
                    <span>{fmt(keyInfo.last_used)}</span>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="api-key-actions">
                <button className="auth-submit-btn" style={{ width: 'auto', display: 'flex', alignItems: 'center', gap: '0.4rem' }} onClick={generateKey}>
                  <RefreshCw size={15} />
                  {keyInfo ? 'Regenerate Key' : 'Generate API Key'}
                </button>
                {keyInfo && (
                  <button className="settings-danger-btn" onClick={revokeKey}>
                    <Trash2 size={15} />
                    Revoke
                  </button>
                )}
              </div>
            </>
          )}
        </div>

        {/* Usage example */}
        <div className="settings-section" style={{ marginTop: '2rem' }}>
          <h2 style={{ marginBottom: '0.75rem', fontSize: '1rem' }}>Usage example</h2>
          <pre className="settings-code">{`# Python
import requests

response = requests.post(
    "http://localhost:8000/chat",
    headers={"Authorization": "Bearer tl-yourkey"},
    json={
        "message": "Explain quantum computing",
        "session_id": "my-session",
        "model": "gemma"   # or "gpt4"
    }
)
print(response.json()["response"])`}
          </pre>
        </div>

      </div>
    </main>
  );
}
