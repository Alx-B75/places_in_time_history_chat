

import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../lib/api.js';

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()
  async function submit(e) {
    e.preventDefault();
    setError('');
    try {
  const base = (import.meta?.env?.VITE_API_BASE || "").replace(/\/+$/, "");
      const body = new URLSearchParams({ username, password });
      const res = await fetch(`${base}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const token = data.access_token;
      localStorage.setItem('token', token);
  navigate('/admin', { replace: true });
    } catch (err) {
      setError(err.message || 'Login failed');
    }
  }
  return (
    <div className="login-page">
      <form onSubmit={submit} className="login-form">
        <h2>Admin Login</h2>
        <label>Username</label>
        <input value={username} onChange={e => setUsername(e.target.value)} placeholder="username" />
        <label>Password</label>
        <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="password" />
        <button type="submit">Login</button>
        {error && <div className="error" style={{color:'red'}}>{error}</div>}
      </form>
    </div>
  )
}
