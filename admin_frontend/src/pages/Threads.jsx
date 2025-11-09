import React, { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext.jsx'

export default function Threads(){
  const { user, loading } = useAuth()
  const [threads, setThreads] = useState([])
  const [err, setErr] = useState('')
  const [creating, setCreating] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    if(loading || !user) return
    ;(async () => {
      try{
        const token = sessionStorage.getItem('userToken') || localStorage.getItem('access_token')
        const res = await fetch(`/threads/user/${user.id}`, {
          headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        })
        if(!res.ok) throw new Error(await res.text())
        const data = await res.json()
        setThreads(data || [])
      }catch(e){ setErr(e.message || 'Failed to load threads') }
    })()
  }, [loading, user])

  if(loading) return <div style={{padding:24}}>Loading…</div>
  if(!user) return <div style={{padding:24}}>Please log in.</div>

  async function createThread(){
    if(!user) return
    setCreating(true)
    setErr('')
    try{
      const token = sessionStorage.getItem('userToken') || localStorage.getItem('access_token')
      const res = await fetch('/threads', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ user_id: user.id })
      })
      if(!res.ok) throw new Error(await res.text())
      const data = await res.json()
      const newId = data.thread_id || data.id
      navigate(`/thread/${newId}`)
    }catch(e){ setErr(e.message || 'Failed to create thread') }
    finally{ setCreating(false) }
  }

  return (
    <div style={{padding:16, maxWidth:800, margin:'0 auto'}}>
      <h2>Your Threads</h2>
      {err ? <div style={{color:'crimson'}}>{err}</div> : null}
      <div style={{marginBottom:12}}>
        <button disabled={creating} onClick={createThread} className="btn btn-primary">
          {creating ? 'Creating…' : 'New Thread'}
        </button>
      </div>
      {threads.length === 0 ? (
        <div style={{color:'#666'}}>No threads yet.</div>
      ) : (
        <ul style={{listStyle:'none', padding:0}}>
          {threads.map(t => (
            <li key={t.id} style={{marginBottom:8}}>
              <Link to={`/thread/${t.id}`}>{t.title || `Thread #${t.id}`}</Link>
              {t.figure_slug ? <small style={{marginLeft:8,color:'#666'}}>({t.figure_slug})</small> : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
