import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function UserLogin(){
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const nav = useNavigate()

  async function submit(e){
    e.preventDefault()
    setErr('')
    try{
      const body = new URLSearchParams({ username: email, password })
      const res = await fetch('/auth/login', { method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'}, body })
      if(!res.ok) throw new Error(await res.text())
      const data = await res.json()
      const token = data.access_token
      try{
        sessionStorage.setItem('userToken', token)
        localStorage.setItem('access_token', token)
      }catch(_){ }
      nav('/dashboard', { replace: true })
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
