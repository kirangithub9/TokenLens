import React, { useState, useEffect, useRef } from 'react';
import { Plus, Settings, Send, User, Paperclip, Trash2, X, FileText, Image, LayoutDashboard, Sun, Moon, LogOut, ShieldCheck, Bot, Key } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { onAuthStateChanged, signOut } from 'firebase/auth';
import { auth } from './firebase';
import AuthPage from './AuthPage';
import MetricsView from './MetricsView';
import SettingsPage from './SettingsPage';
import AdminPage from './AdminPage';
import AgentRunsPage from './AgentRunsPage';
import ApiKeyPage from './ApiKeyPage';
import alumnxLogo from './assets/alumnxlogo_new.png';
import './index.css';

const MAX_FILE_SIZE = 3 * 1024 * 1024;
const ALLOWED_TYPES = ['application/pdf', 'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/svg+xml'];
const MODEL_PRICING = {
  gemma: { input: 0.10 / 1_000_000, output: 0.40  / 1_000_000, label: 'Gemma' },
  gpt4:  { input: 0.15 / 1_000_000, output: 0.60  / 1_000_000, label: 'GPT-4o Mini' },
};

function App() {
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

  const [currentUser, setCurrentUser] = useState(undefined); // undefined = loading
  const [isAdmin, setIsAdmin]         = useState(false);

  useEffect(() => {
    const unsub = onAuthStateChanged(auth, async (user) => {
      setCurrentUser(user);
      if (user) {
        try {
          const token = await user.getIdToken();
          const signupOrg  = localStorage.getItem('signup_organization') || null;
          const signupRole = localStorage.getItem('signup_role') || null;
          localStorage.removeItem('signup_organization');
          localStorage.removeItem('signup_role');
          // Register user in DB on every login; pass signup profile fields on first registration
          await fetch(`${API_BASE_URL}/admin/register`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ organization: signupOrg, role: signupRole }),
          });
          // Check admin status
          const res = await fetch(`${API_BASE_URL}/admin/check`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (res.ok) {
            const data = await res.json();
            setIsAdmin(data.is_admin === true);
          }
        } catch {
          setIsAdmin(false);
        }
      } else {
        setIsAdmin(false);
      }
    });
    return unsub;
  }, []);

  const getToken = async () => {
    if (!currentUser) return null;
    return currentUser.getIdToken();
  };

  const [conversations, setConversations] = useState(() => {
    const saved = localStorage.getItem('gemma_conversations');
    if (saved) return JSON.parse(saved);
    
    // Migrate single chat history from previous versions:
    const oldHistory = localStorage.getItem('gemma_chat_history');
    const oldSessionId = localStorage.getItem('gemma_session_id');
    if (oldHistory && oldSessionId) {
      try {
        const messagesArray = JSON.parse(oldHistory);
        if (messagesArray.length > 0) {
          const firstUser = messagesArray.find(m => m.role === 'user')?.content || '';
          const initialTitle = firstUser ? (firstUser.length > 25 ? firstUser.slice(0, 25) + '...' : firstUser) : 'Previous Chat';
          const migrated = [{
            id: oldSessionId,
            title: initialTitle,
            messages: messagesArray,
            timestamp: Date.now()
          }];
          localStorage.setItem('gemma_conversations', JSON.stringify(migrated));
          return migrated;
        }
      } catch (err) {
        console.error('Migration failed:', err);
      }
    }
    return [];
  });

  const [sesssionId, setSessionId] = useState(() => {
    const saved = localStorage.getItem('gemma_session_id');
    if (saved) return saved;
    const newId = 'sess-' + Date.now();
    localStorage.setItem('gemma_session_id', newId);
    return newId;
  });

  const [messages, setMessages] = useState(() => {
    const savedSessionId = localStorage.getItem('gemma_session_id');
    if (savedSessionId) {
      const savedConversations = localStorage.getItem('gemma_conversations');
      if (savedConversations) {
        try {
          const list = JSON.parse(savedConversations);
          const active = list.find(c => c.id === savedSessionId);
          if (active) return active.messages;
        } catch (err) {
          console.error('Failed to load active conversation:', err);
        }
      }
    }
    return [];
  });

  const userId = currentUser?.uid ?? null;

  const [input, setInput] = useState('');
  const [selectedModel, setSelectedModel] = useState('gemma');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileError, setFileError] = useState('');
  const [uploadProgress, setUploadProgress] = useState(null); // null = not uploading
  const [view, setView] = useState('chat');
  const [metricsData, setMetricsData] = useState(() => {
    const saved = localStorage.getItem('gemma_metrics');
    return saved ? JSON.parse(saved) : [];
  });
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('gemma_theme');
    return saved ? saved : 'dark';
  });

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    localStorage.setItem('gemma_theme', theme);
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // Sync active messages to multi-conversation state and LocalStorage:
  useEffect(() => {
    localStorage.setItem('gemma_session_id', sesssionId);
  }, [sesssionId]);

  useEffect(() => {
    if (messages.length === 0) return;
    
    setConversations(prev => {
      const existingIdx = prev.findIndex(c => c.id === sesssionId);
      let updated;
      if (existingIdx !== -1) {
        updated = prev.map((c, i) => i === existingIdx ? { ...c, messages, timestamp: Date.now() } : c);
      } else {
        const firstUserMessage = messages.find(m => m.role === 'user')?.content || '';
        const title = firstUserMessage ? (firstUserMessage.length > 25 ? firstUserMessage.slice(0, 25) + '...' : firstUserMessage) : 'New Chat';
        updated = [
          { id: sesssionId, title, messages, timestamp: Date.now() },
          ...prev
        ];
      }
      localStorage.setItem('gemma_conversations', JSON.stringify(updated));
      return updated;
    });
  }, [messages, sesssionId]);

  useEffect(() => {
    localStorage.setItem('gemma_metrics', JSON.stringify(metricsData));
  }, [metricsData]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };
  useEffect(() => { scrollToBottom(); }, [messages, isLoading]);

  useEffect(() => {
    if (!fileError) return;
    const t = setTimeout(() => setFileError(''), 3000);
    return () => clearTimeout(t);
  }, [fileError]);

  const handleInput = (e) => {
    setInput(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const isPdf = ALLOWED_TYPES.includes(file.type) || file.name.toLowerCase().endsWith('.pdf');
    if (!isPdf) {
      setFileError('Only PDF files are allowed.');
      e.target.value = '';
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      setFileError('File must be smaller than 3 MB.');
      e.target.value = '';
      return;
    }
    setSelectedFile(file);
    setFileError('');
    e.target.value = '';
  };

  const removeFile = () => setSelectedFile(null);

  const estimateTokens = (text) => Math.ceil((text || '').length / 4);

  const handleSend = async (e) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;
    if (selectedFile && !trimmed) {
      setFileError('Please type a message along with your file.');
      return;
    }

    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';

    const newMessage = { role: 'user', content: trimmed };
    if (selectedFile) {
      if (isImageFile(selectedFile)) {
        try {
          const dataURL = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(new Error('Failed to read image file'));
            reader.readAsDataURL(selectedFile);
          });
          newMessage.image = dataURL;
          newMessage.fileName = selectedFile.name;
        } catch (error) {
          console.error('Error reading image:', error);
          newMessage.content = `📎 ${selectedFile.name} (preview failed)\n\n${trimmed}`;
          newMessage.fileName = selectedFile.name;
        }
      } else {
        newMessage.content = `📎 ${selectedFile.name}\n\n${trimmed}`;
        newMessage.fileName = selectedFile.name;
      }
    }

    setMessages(prev => [...prev, newMessage]);
    setIsLoading(true);
    const startTime = Date.now();

    try {
      let data;

      if (selectedFile) {
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('message', trimmed);
        formData.append('session_id', sesssionId);
        formData.append('user_id', userId);
        formData.append('model', selectedModel);

        setUploadProgress(0);
        const fileToken = await getToken();
        data = await new Promise((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.open('POST', `${API_BASE_URL}/chat-file`);
          if (fileToken) xhr.setRequestHeader('Authorization', `Bearer ${fileToken}`);
          xhr.upload.onprogress = (ev) => {
            if (ev.lengthComputable) setUploadProgress(Math.round((ev.loaded / ev.total) * 100));
          };
          xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
              try { resolve(JSON.parse(xhr.responseText)); }
              catch { reject(new Error('Invalid response from server')); }
            } else {
              reject(new Error('Failed to process file'));
            }
          };
          xhr.onerror = () => reject(new Error('Failed to process file'));
          xhr.send(formData);
        });
      } else {
        const token = await getToken();
        const response = await fetch(`${API_BASE_URL}/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ message: trimmed, session_id: sesssionId, user_id: userId, model: selectedModel }),
        });
        if (!response.ok) throw new Error('Failed to connect to Gemma E4B');
        data = await response.json();
      }
      const latencyMs = Date.now() - startTime;
      const currentTextTokens = estimateTokens(trimmed);
      const currentAttachmentTokens = selectedFile 
        ? (selectedFile.name.toLowerCase().endsWith('.pdf') 
            ? Math.min(1500, Math.ceil(selectedFile.size / 8)) 
            : 250) 
        : 0;
      const pTok = currentTextTokens + currentAttachmentTokens;
      
      const cTok = data.usage?.completion_tokens ?? data.completion_tokens ?? data.output_tokens ?? estimateTokens(data.response);
      const pricing = MODEL_PRICING[selectedModel] ?? MODEL_PRICING.gemma;
      
      const INR_RATE = 84.5;
      const textTokens = currentTextTokens;
      const attachmentTokens = currentAttachmentTokens;
      
      const inputCostUsd = pTok * pricing.input;
      const inputCostInr = inputCostUsd * INR_RATE;
      
      const outputCostUsd = cTok * pricing.output;
      const outputCostInr = outputCostUsd * INR_RATE;
      
      const totalCostUsd = inputCostUsd + outputCostUsd;
      const totalCostInr = totalCostUsd * INR_RATE;
      setMetricsData(prev => [...prev, {
        id: `m-${Date.now()}`,
        timestamp: Date.now(),
        prompt_tokens: pTok,
        completion_tokens: cTok,
        total_tokens: pTok + cTok,
        latency_ms: latencyMs,
        model: selectedModel,
        cost_usd: totalCostUsd,
      }]);

      setMessages(prev => [...prev, { 
        role: 'bot', 
        content: data.response,
        metrics: {
          inputTextTokens: textTokens,
          inputAttachmentTokens: attachmentTokens,
          outputTokens: cTok,
          latencyMs: latencyMs,
          inputCostUsd,
          inputCostInr,
          outputCostUsd,
          outputCostInr,
          totalCostUsd,
          totalCostInr,
          modelLabel: pricing.label
        }
      }]);
    } catch (error) {
      setMessages(prev => [...prev, { role: 'system', content: 'Oops! ' + error.message }]);
    } finally {
      setIsLoading(false);
      setSelectedFile(null);
      setUploadProgress(null);
    }
  };

  const switchConversation = (id) => {
    const active = conversations.find(c => c.id === id);
    if (active) {
      setSessionId(id);
      setMessages(active.messages);
      setView('chat');
    }
  };

  const deleteConversation = (id, e) => {
    e.stopPropagation();
    if (window.confirm('Delete this conversation?')) {
      const updated = conversations.filter(c => c.id !== id);
      setConversations(updated);
      localStorage.setItem('gemma_conversations', JSON.stringify(updated));
      
      if (sesssionId === id) {
        if (updated.length > 0) {
          setSessionId(updated[0].id);
          setMessages(updated[0].messages);
        } else {
          setSessionId('sess-' + Date.now());
          setMessages([]);
        }
      }
    }
  };

  const clearAllConversations = () => {
    if (window.confirm('Are you sure you want to clear ALL conversations?')) {
      setConversations([]);
      localStorage.removeItem('gemma_conversations');
      setMessages([]);
      setSessionId('sess-' + Date.now());
    }
  };

  const isImageFile = (file) => file?.type?.startsWith('image/');

  if (currentUser === undefined) {
    return <div className="auth-page"><div className="auth-card"><p style={{ color: 'var(--text-secondary)' }}>Loading...</p></div></div>;
  }

  if (!currentUser) {
    return <AuthPage />;
  }

  return (
    <div className="app-container">
      {/* ========== Sidebar ========== */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="logo">
            <img src={alumnxLogo} alt="AlumnxLabs" className="logo-img" />
          </div>
          <button
            className="new-chat-btn"
            onClick={() => {
              setMessages([]);
              setSelectedFile(null);
              setSessionId('sess-' + Date.now());
              setView('chat');
            }}
          >
            <Plus size={18} /> New Chat
          </button>
        </div>

        <div className="chat-history">
          {!conversations.some(c => c.id === sesssionId) && (
            <div className="history-item-container active">
              <span className="history-item-title">💬 New Chat...</span>
            </div>
          )}
          {conversations.map(c => (
            <div
              key={c.id}
              className={`history-item-container ${c.id === sesssionId && view === 'chat' ? 'active' : ''}`}
              onClick={() => switchConversation(c.id)}
            >
              <span className="history-item-title">💬 {c.title}</span>
              <button
                className="history-delete-btn"
                onClick={(e) => deleteConversation(c.id, e)}
                title="Delete Chat"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>

        {/* ===== Bottom navigation ===== */}
        <div className="sidebar-nav">
          <button
            className={`dashboard-nav-btn ${view === 'metrics' ? 'active' : ''}`}
            onClick={() => setView('metrics')}
          >
            <LayoutDashboard size={15} />
            <span>TokenLens</span>
            {metricsData.length > 0 && (
              <span className="dashboard-nav-badge">{metricsData.length}</span>
            )}
          </button>
          <button
            className={`dashboard-nav-btn ${view === 'agents' ? 'active' : ''}`}
            onClick={() => setView('agents')}
          >
            <Bot size={15} />
            <span>Agent Runs</span>
          </button>
          <button
            className={`dashboard-nav-btn ${view === 'apikey' ? 'active' : ''}`}
            onClick={() => setView('apikey')}
          >
            <Key size={15} />
            <span>API Key</span>
          </button>
          {isAdmin && (
            <button
              className={`dashboard-nav-btn ${view === 'admin' ? 'active' : ''}`}
              onClick={() => setView('admin')}
            >
              <ShieldCheck size={15} />
              <span>Admin</span>
            </button>
          )}
{(conversations.length > 0 || messages.length > 0) && (
            <button className="dashboard-nav-btn nav-danger" onClick={clearAllConversations}>
              <Trash2 size={15} />
              <span>Clear History</span>
            </button>
          )}
        </div>

        <div className="sidebar-footer">
          <div className="user-profile">
            <div className="avatar">
              {currentUser?.photoURL
                ? <img src={currentUser.photoURL} alt="avatar" style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }} />
                : (currentUser?.displayName?.[0] ?? currentUser?.email?.[0] ?? 'U').toUpperCase()
              }
            </div>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {currentUser?.displayName || currentUser?.email || 'User'}
            </span>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              className="settings-icons"
              title="Settings"
              onClick={() => setView('settings')}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: view === 'settings' ? 'var(--accent)' : 'inherit' }}
            >
              <Settings size={18} />
            </button>
            <button
              className="settings-icons"
              title="Sign out"
              onClick={() => signOut(auth)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit' }}
            >
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </aside>

      {/* ========== Main Content ========== */}
      {view === 'settings' ? (
        <SettingsPage theme={theme} setTheme={setTheme} />
      ) : view === 'admin' ? (
        <AdminPage getToken={getToken} />
      ) : view === 'agents' ? (
        <AgentRunsPage getToken={getToken} />
      ) : view === 'apikey' ? (
        <ApiKeyPage getToken={getToken} />
      ) : view === 'metrics' ? (
        <MetricsView
          metrics={metricsData}
          onClearMetrics={() => setMetricsData([])}
          theme={theme}
          setTheme={setTheme}
        />
      ) : (
        <main className="main-chat">
          <header className="chat-header">
            <div className="header-title">
              <div className="header-title-icon">T</div>
              <h1>TOKENLENS</h1>
            </div>
            <button
              onClick={() => setTheme(prev => prev === 'dark' ? 'light' : 'dark')}
              className="theme-toggle-btn"
              title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
            >
              {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
            </button>
          </header>

          <div className="messages-container">
            {messages.length === 0 ? (
              <div className="message system-message">
                <div className="message-content">
                  <div className="bot-avatar">G</div>
                  <div className="text">
                    <h2>Hello! I'm Gemma E4B.</h2>
                    <p>Ask me anything or attach a PDF / image to get started.</p>
                    <div className="suggestions">
                      {['Compare these two ideas...', 'Write a story about a robot', 'Help me debug this React code'].map(s => (
                        <button key={s} className="suggestion-chip" onClick={() => setInput(s)}>{s}</button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              messages.map((m, i) => (
                <div key={i} className={`message ${m.role}-message`}>
                  <div className="message-content">
                    <div className={m.role === 'user' ? 'user-avatar' : 'bot-avatar'}>
                      {m.role === 'user' ? <User size={20} /> : 'G'}
                    </div>
                    <div className="text">
                      {m.image && (
                        <img
                          src={m.image}
                          alt={m.fileName || 'uploaded image'}
                          style={{
                            maxWidth: '100%',
                            height: 'auto',
                            borderRadius: '8px',
                            margin: '1rem 0',
                            boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
                            display: 'block',
                          }}
                        />
                      )}
                      <ReactMarkdown components={{
                        img: ({ src, alt }) => (
                          <img
                            src={src}
                            alt={alt}
                            style={{
                              maxWidth: '240px',
                              maxHeight: '160px',
                              objectFit: 'cover',
                              borderRadius: '8px',
                              margin: '0.5rem 0',
                              boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
                              display: 'block',
                            }}
                          />
                        ),
                      }}>{m.content}</ReactMarkdown>
                      {m.role === 'bot' && m.metrics && (
                        <div className="message-metrics">
                          <div className="metrics-header-row">
                            <span className="metrics-title">⚡ METRICS ({m.metrics?.modelLabel || 'Gemma'})</span>
                            <span className="metrics-latency">⏱️ {(m.metrics?.latencyMs ?? 0) >= 1000 ? `${((m.metrics?.latencyMs ?? 0) / 1000).toFixed(2)}s` : `${m.metrics?.latencyMs ?? 0}ms`}</span>
                          </div>
                          <div className="metrics-row-grid">
                            <div className="metric-chip">
                              <span className="metric-chip-label">Input Text</span>
                              <span className="metric-chip-val">{m.metrics?.inputTextTokens ?? 0} Tokens</span>
                            </div>
                            <div className="metric-chip">
                              <span className="metric-chip-label">Input Attachments</span>
                              <span className="metric-chip-val">{m.metrics?.inputAttachmentTokens ?? 0} Tokens</span>
                            </div>
                            <div className="metric-chip">
                              <span className="metric-chip-label">Output Tokens</span>
                              <span className="metric-chip-val">{m.metrics?.outputTokens ?? 0} Tokens</span>
                            </div>
                          </div>
                          <div className="metrics-cost-section">
                            <div className="cost-breakdown-row">
                              <div className="cost-breakdown-col">
                                <span className="cost-lbl">Input Cost</span>
                                <span className="cost-val-usd">${(m.metrics?.inputCostUsd ?? 0).toFixed(6)}</span>
                                <span className="cost-val-inr">₹{(m.metrics?.inputCostInr ?? 0).toFixed(4)}</span>
                              </div>
                              <div className="cost-breakdown-col">
                                <span className="cost-lbl">Output Cost</span>
                                <span className="cost-val-usd">${(m.metrics?.outputCostUsd ?? 0).toFixed(6)}</span>
                                <span className="cost-val-inr">₹{(m.metrics?.outputCostInr ?? 0).toFixed(4)}</span>
                              </div>
                              <div className="cost-breakdown-col highlight">
                                <span className="cost-lbl">Total Cost</span>
                                <span className="cost-val-usd font-bold">${(m.metrics?.totalCostUsd ?? 0).toFixed(6)}</span>
                                <span className="cost-val-inr font-bold">₹{(m.metrics?.totalCostInr ?? 0).toFixed(4)}</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
            {isLoading && (
              <div className="message bot-message">
                <div className="message-content">
                  <div className="bot-avatar">G</div>
                  <div className="typing">
                    <span></span><span></span><span></span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* ========== Input Area ========== */}
          <footer className="input-area">
            <form onSubmit={handleSend} className="chat-input-container">
              {fileError && (
                <div className="file-error">
                  <span>{fileError}</span>
                  <button type="button" onClick={() => setFileError('')}><X size={14} /></button>
                </div>
              )}

              {selectedFile && (
                <div className="file-preview">
                  {isImageFile(selectedFile) ? <Image size={16} /> : <FileText size={16} />}
                  <span className="file-name">{selectedFile.name}</span>
                  <span className="file-size">({(selectedFile.size / 1024).toFixed(0)} KB)</span>
                  {uploadProgress !== null ? (
                    <div className="upload-progress">
                      <div className="upload-progress-track">
                        <div className="upload-progress-bar" style={{ width: `${uploadProgress}%` }} />
                      </div>
                      <span className="upload-progress-label">{uploadProgress}%</span>
                    </div>
                  ) : (
                    <button type="button" className="file-remove" onClick={removeFile}><X size={14} /></button>
                  )}
                </div>
              )}

              <div className="input-wrapper">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={handleInput}
                  placeholder={`Message ${selectedModel === 'gpt4' ? 'GPT-4o Mini' : 'TokenLens'}...`}
                  rows="1"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSend(e);
                    }
                  }}
                />
                <div className="input-actions">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="application/pdf,.pdf"
                    onChange={handleFileSelect}
                    style={{ display: 'none' }}
                  />
                  <select
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    className="model-select"
                  >
                    <option value="gemma">Gemma</option>
                    <option value="gpt4">GPT-4o Mini</option>
                  </select>
                  <button
                    type="button"
                    className={`tool-btn ${selectedFile ? 'tool-btn-active' : ''}`}
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isLoading}
                    title="Attach a PDF (max 10 MB)"
                  >
                    <Paperclip size={18} />
                  </button>
                  <button type="submit" className="send-btn" disabled={!input.trim() || isLoading}>
                    <Send size={16} />
                  </button>
                </div>
              </div>
              <p className="disclaimer">{selectedModel === 'gpt4' ? 'GPT-4o Mini' : 'Gemma E4B'} can make mistakes. Check important info.</p>
            </form>
          </footer>
        </main>
      )}
    </div>
  );
}

export default App;
