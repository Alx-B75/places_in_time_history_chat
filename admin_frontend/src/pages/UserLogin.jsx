import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext.jsx'

export default function UserLogin(){
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const nav = useNavigate()
  const { setToken, refresh } = useAuth()
  async function attemptGuestUpgrade(bearer){
    try{
      const res = await fetch('/guest/upgrade', {
        method:'POST',
        headers:{ 'Authorization': `Bearer ${bearer}` },
        credentials:'include',
      })
      if(!res.ok) return null
      const data = await res.json().catch(()=>null)
      return data && data.upgraded ? data : null
    }catch(_){ return null }
  }

  async function submit(e){
    e.preventDefault()
    setErr('')
    try{
  const res = await fetch('/auth/login', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ username: email, password }) })
      if(!res.ok) throw new Error(await res.text())
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
    <div style={{padding:24, maxWidth:420, margin:'40px auto'}}>
      <h2>User Login</h2>
      <form onSubmit={submit}>
        <label>Email</label>
        <input value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com" />
        <label>Password</label>
        <input type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="••••••••" />
        <button type="submit">Sign in</button>
        {err ? <div style={{color:'crimson', marginTop:8}}>{err}</div> : null}
      </form>
    </div>
  )
}
