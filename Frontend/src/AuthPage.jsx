import React, { useState } from 'react';
import {
  signInWithPopup,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  updateProfile,
} from 'firebase/auth';
import { auth, googleProvider } from './firebase';
import alumnxLogo from './assets/alumnxlogo_new.png';

export default function AuthPage() {
  const [mode, setMode] = useState('signin'); // 'signin' | 'signup'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [name, setName] = useState('');
  const [organization, setOrganization] = useState('');
  const [role, setRole] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const clearError = () => setError('');

  const handleGoogle = async () => {
    setLoading(true);
    clearError();
    try {
      await signInWithPopup(auth, googleProvider);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleEmailAuth = async (e) => {
    e.preventDefault();
    if (mode === 'signup' && password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    clearError();
    try {
      if (mode === 'signup') {
        const cred = await createUserWithEmailAndPassword(auth, email, password);
        if (name.trim()) {
          await updateProfile(cred.user, { displayName: name.trim() });
        }
        if (organization.trim()) localStorage.setItem('signup_organization', organization.trim());
        if (role) localStorage.setItem('signup_role', role);
      } else {
        await signInWithEmailAndPassword(auth, email, password);
      }
    } catch (e) {
      setError(friendlyError(e.code));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <img src={alumnxLogo} alt="AlumnxLabs" className="logo-img" />
        </div>
        <h1 className="auth-title">TOKENLENS</h1>
        <p className="auth-subtitle">
          {mode === 'signin' ? 'Sign in to continue' : 'Create your account'}
        </p>

        {error && <div className="auth-error">{error}</div>}

        <button className="google-btn" onClick={handleGoogle} disabled={loading}>
          <GoogleIcon />
          Continue with Google
        </button>

        <div className="auth-divider"><span>or</span></div>

        <form onSubmit={handleEmailAuth} className="auth-form">
          {mode === 'signup' && (
            <input
              type="text"
              placeholder="Full name"
              value={name}
              onChange={e => setName(e.target.value)}
              required
              className="auth-input"
              autoComplete="name"
            />
          )}
          {mode === 'signup' && (
            <input
              type="text"
              placeholder="Organization / Company (optional)"
              value={organization}
              onChange={e => setOrganization(e.target.value)}
              className="auth-input"
              autoComplete="organization"
            />
          )}
          {mode === 'signup' && (
            <select
              value={role}
              onChange={e => setRole(e.target.value)}
              className="auth-input"
            >
              <option value="">Select your role (optional)</option>
              <option value="developer">Developer / Engineer</option>
              <option value="data_scientist">Data Scientist</option>
              <option value="ml_engineer">ML Engineer</option>
              <option value="product_manager">Product Manager</option>
              <option value="devops">DevOps / SRE</option>
              <option value="other">Other</option>
            </select>
          )}
          <input
            type="email"
            placeholder="Email address"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            className="auth-input"
            autoComplete="email"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            minLength={6}
            className="auth-input"
            autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
          />
          {mode === 'signup' && (
            <input
              type="password"
              placeholder="Confirm password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              required
              minLength={6}
              className="auth-input"
              autoComplete="new-password"
            />
          )}
          <button type="submit" className="auth-submit-btn" disabled={loading}>
            {loading ? 'Please wait...' : mode === 'signin' ? 'Sign In' : 'Create Account'}
          </button>
        </form>

        <p className="auth-switch">
          {mode === 'signin' ? (
            <>Don't have an account?{' '}
              <button className="auth-link" onClick={() => { setMode('signup'); clearError(); setConfirmPassword(''); setOrganization(''); setRole(''); }}>
                Sign up
              </button>
            </>
          ) : (
            <>Already have an account?{' '}
              <button className="auth-link" onClick={() => { setMode('signin'); clearError(); setConfirmPassword(''); }}>
                Sign in
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg">
      <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z" fill="#4285F4"/>
      <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
      <path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
      <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
    </svg>
  );
}

function friendlyError(code) {
  const map = {
    'auth/user-not-found':        'No account found with this email.',
    'auth/wrong-password':        'Incorrect password.',
    'auth/invalid-credential':    'Incorrect email or password.',
    'auth/email-already-in-use':  'An account with this email already exists.',
    'auth/weak-password':         'Password must be at least 6 characters.',
    'auth/invalid-email':         'Please enter a valid email address.',
    'auth/too-many-requests':     'Too many attempts. Please try again later.',
    'auth/popup-closed-by-user':  'Sign-in popup was closed.',
    'auth/operation-not-allowed': 'Email/password sign-in is not enabled. Contact the administrator.',
    'auth/network-request-failed':'Network error. Check your connection and try again.',
  };
  return map[code] || `Something went wrong (${code || 'unknown'}). Please try again.`;
}
