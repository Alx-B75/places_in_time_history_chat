import React, { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext.jsx'
import LogoCard from '../components/LogoCard.jsx'

export default function Threads(){
  const { user, loading } = useAuth()
  const [threads, setThreads] = useState([])
  const [err, setErr] = useState('')
  const [creating, setCreating] = useState(false)
  const [figuresMap, setFiguresMap] = useState({}) // slug -> figure detail
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

  // Fetch figure details for any slugs present to show thumbnails/names
  useEffect(() => {
    const slugs = Array.from(new Set((threads || []).map(t => t.figure_slug).filter(Boolean)))
    if (slugs.length === 0) return
    let cancelled = false
    ;(async () => {
      const map = {}
      await Promise.all(slugs.map(async (slug) => {
        try{
          const r = await fetch(`/figures/${encodeURIComponent(slug)}`)
          if(r.ok){ map[slug] = await r.json() }
        }catch(_){ /* ignore */ }
      }))
      if(!cancelled) setFiguresMap(map)
    })()
    return () => { cancelled = true }
  }, [threads])

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

  async function deleteThread(threadId){
    if(!user) return
    const proceed = window.confirm('Are you sure you want to delete this thread? This cannot be undone.')
    if(!proceed) return
    try{
      const token = sessionStorage.getItem('userToken') || localStorage.getItem('access_token')
      const res = await fetch(`/threads/${threadId}`, {
        method: 'DELETE',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {}
      })
      if(!res.ok && res.status !== 204){
        const text = await res.text()
        throw new Error(text || 'Failed to delete thread')
      }
      setThreads(prev => (prev || []).filter(t => t.id !== threadId))
    }catch(e){ setErr(e.message || 'Failed to delete thread') }
  }

  return (
    <div className="wrap" style={{maxWidth:980}}>
      <div style={{cursor:'pointer'}} onClick={()=>navigate('/dashboard')} title="Back to Dashboard" className="logo-wide">
        <LogoCard wide />
      </div>
      <div className="banner" style={{margin:'8px 0', justifyContent:'space-between'}}>
        <div className="brand-title">
          <h1 style={{margin:0}}>Your Threads</h1>
          <div className="muted">Manage and revisit your conversations</div>
        </div>
        <div className="banner-actions">
          <button className="btn sm" onClick={()=>navigate('/dashboard')}>← Back</button>
          <button onClick={()=>navigate('/figures')} className="btn btn-primary">New Thread</button>
        </div>
      </div>
      {err ? <div className="muted" style={{color:'#fca5a5'}}>{err}</div> : null}
      <div className="card panel" style={{padding:18}}>
        {threads.length === 0 ? (
          <div className="muted">No threads yet.</div>
        ) : (
          <ul style={{listStyle:'none', padding:0, margin:0, display:'flex', flexDirection:'column', gap:10}}>
            {threads.map(t => {
              const fig = t.figure_slug ? figuresMap[t.figure_slug] : null
              return (
                <li key={t.id} className="thread-item">
                  <div style={{flex:1, display:'flex', alignItems:'center', gap:12}}>
                    {fig?.image_url ? (
                      <img src={fig.image_url} alt={fig.name} className="thread-thumb" />
                    ) : null}
                    <div className="thread-text" style={{display:'flex', flexDirection:'column'}}>
                      <Link to={`/thread/${t.id}`} style={{color:'var(--accent)', fontSize:'var(--fs-md)', textDecoration:'none'}}>
                        {t.title || `Thread #${t.id}`}
                      </Link>
                      <div className="muted" style={{fontSize:'var(--fs-sm)'}}>
                        {fig ? fig.name : (t.figure_slug || '')}
                      </div>
                      {t.first_user_message ? (
                        <div className="muted" style={{fontSize:'var(--fs-sm)', opacity:.9, marginTop:4}}>
                          {t.first_user_message.length > 140 ? `${t.first_user_message.slice(0, 140)}…` : t.first_user_message}
                        </div>
                      ) : null}
                    </div>
                  </div>
                  <div className="thread-actions">
                    <button className="btn sm" onClick={()=>navigate(`/thread/${t.id}`)} style={{fontSize:'var(--fs-sm)'}}>Open →</button>
                    <button className="btn sm" onClick={()=>deleteThread(t.id)} style={{fontSize:'var(--fs-sm)'}}>Delete</button>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
