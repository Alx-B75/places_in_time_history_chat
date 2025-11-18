import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext.jsx'
import LogoCard from '../components/LogoCard.jsx'
import { apiFetch } from '../lib/apiFetch.js'

export default function UserLogin(){
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const nav = useNavigate()
  const { setToken, refresh } = useAuth()
  async function attemptGuestUpgrade(bearer){
    try{
      const res = await apiFetch('/guest/upgrade', {
        method:'POST',
        headers:{ 'Authorization': `Bearer ${bearer}` },
        credentials:'include'
      })
      const data = await res.json().catch(()=>null)
      return data && data.upgraded ? data : null
    }catch(_){ return null }
  }

  async function submit(e){
    e.preventDefault()
    setErr('')
    try{
      const res = await apiFetch('/auth/login', {
        method:'POST',
        body: JSON.stringify({ username: email, password }),
        credentials:'include'
      })
      const data = await res.json()
      const token = data.access_token
      try{
        sessionStorage.setItem('userToken', token)
        localStorage.setItem('access_token', token)
        // also set a host-scoped cookie for cross-port dev access
        document.cookie = `pit_access_token=${token}; path=/`
      }catch(_){ }
      // update context immediately so downstream routes see authenticated state
      try{ setToken(token) }catch(_){ }
      // Trigger refresh first so dashboard has user data immediately.
      try{ await refresh() }catch(_){ }
      // Try upgrading guest transcript if present
      const up = await attemptGuestUpgrade(token)
      if(up && up.thread_id){
        // Pass state so ThreadView knows this came from a guest upgrade and should send Back to dashboard.
        nav(`/thread/${up.thread_id}`, { replace: true, state: { fromGuestUpgrade: true } })
      }else{
        nav('/dashboard', { replace: true })
      }
    }catch(e){ setErr(e.message || 'Login failed') }
  }

  return (
    <div className="wrap" style={{maxWidth:560}}>
      <LogoCard wide />
      <div className="banner" style={{margin:'8px 0'}}>
        <div className="brand-title"><h1 style={{margin:0}}>Sign in</h1><div className="muted">Access your dashboard and threads</div></div>
      </div>
      <div className="card panel" style={{padding:18}}>
        <form onSubmit={submit} className="stack">
          <label>Email</label>
          <input className="pit-input" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com" />
          <label>Password</label>
          <input className="pit-input" type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="••••••••" />
          <button className="btn btn-primary" type="submit">Sign in</button>
          {err ? <div className="muted" style={{color:'#fca5a5'}}>{err}</div> : null}
        </form>
      </div>
    </div>
  )
}
