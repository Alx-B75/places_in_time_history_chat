import React, { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext.jsx'
import LogoCard from '../components/LogoCard.jsx'

export default function UserRegister(){
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [gdpr, setGdpr] = useState(false)
  const [aiAck, setAiAck] = useState(false)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
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

  function validEmail(e){ return /[^\s@]+@[^\s@]+\.[^\s@]+/.test(e) }
  function strongEnough(p){ return /[A-Z]/.test(p) && /[a-z]/.test(p) && /[0-9]/.test(p) && /[^A-Za-z0-9]/.test(p) && p.length>=8 }

  async function submit(e){
    e.preventDefault()
    setErr('')
    if(!validEmail(email)) { setErr('Enter a valid email.'); return }
    if(!strongEnough(password)) { setErr('Password must include upper, lower, number, special and be 8+ chars.'); return }
    if(!gdpr || !aiAck){ setErr('Please accept the GDPR consent and AI disclosure.'); return }

    setBusy(true)
    try{
      const res = await fetch('/auth/register', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email, password, gdpr_consent: gdpr, ai_ack: aiAck }) })
      if(!res.ok) throw new Error(await res.text())
      const data = await res.json()
      const token = data.access_token
      try{
        sessionStorage.setItem('userToken', token)
        localStorage.setItem('access_token', token)
        document.cookie = `pit_access_token=${token}; path=/`
      }catch(_){ }
      try{ setToken(token) }catch(_){ }
      try{ await refresh() }catch(_){ }
      // Try to carry over guest session transcript if present
      const up = await attemptGuestUpgrade(token)
      if(up && up.thread_id){
        nav(`/thread/${up.thread_id}`, { replace: true, state: { fromGuestUpgrade: true } })
      }else{
        nav('/dashboard', { replace: true })
      }
    }catch(e){ setErr(e.message || 'Registration failed') }
    finally{ setBusy(false) }
  }

  return (
    <div className="wrap" style={{maxWidth:640}}>
      <LogoCard wide />
      <div className="banner" style={{margin:'8px 0'}}>
        <div className="brand-title"><h1 style={{margin:0}}>Create your account</h1><div className="muted">Continue your guest conversation and save threads</div></div>
      </div>
      <div className="card panel" style={{padding:18}}>
        <form onSubmit={submit} className="stack">
          <label>Email</label>
          <input className="pit-input" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com" />
          <label>Password</label>
          <input className="pit-input" type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Strong password" />
          <label className="row" style={{alignItems:'flex-start', gap:8}}>
            <input type="checkbox" checked={gdpr} onChange={e=>setGdpr(e.target.checked)} />
            <span>
              I consent to processing of my data in line with the privacy policy (GDPR). 
              <a href="/policy/gdpr" style={{marginLeft:6}}>See policy</a>.
            </span>
          </label>
          <label className="row" style={{alignItems:'flex-start', gap:8}}>
            <input type="checkbox" checked={aiAck} onChange={e=>setAiAck(e.target.checked)} />
            <span>
              I understand that answers are created by referencing historically checked facts, cross‑referenced with creative AI. 
              <a href="/policy/ai" style={{marginLeft:6}}>See policy</a> for more information.
            </span>
          </label>
          <button className="btn btn-primary" type="submit" disabled={busy}>{busy?'Creating…':'Create account'}</button>
          {err ? <div className="muted" style={{color:'#fca5a5'}}>{err}</div> : null}
        </form>
        <div style={{marginTop:12}}>Already have an account? <Link to="/login">Sign in</Link></div>
      </div>
    </div>
  )
}
