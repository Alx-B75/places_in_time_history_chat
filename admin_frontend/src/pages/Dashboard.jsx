import React, { useEffect, useState } from 'react'
import { useInteraction } from '../contexts/InteractionContext'
import { useAuth } from '../contexts/AuthContext.jsx'
import { useNavigate } from 'react-router-dom'
import LogoCard from '../components/LogoCard.jsx'

const TOPICS = ['Ancient Egypt','World Wars','Industrial Revolution','Renaissance','Space Age']

function SectionCard({title, children}){
  return (
    <div style={{background:'#fff',padding:16,borderRadius:12,boxShadow:'0 2px 10px rgba(0,0,0,0.06)',marginBottom:12}}>
      <h3 style={{margin:'0 0 8px 0'}}>{title}</h3>
      <div>{children}</div>
    </div>
  )
}

export default function Dashboard(){
  const { user, loading, token } = useAuth()
  const { mode, setMode } = useInteraction()
  const navigate = useNavigate()
  const [creating, setCreating] = useState(false)
  const [err, setErr] = useState('')
  const [favs, setFavs] = useState([])
  const [favDetails, setFavDetails] = useState([])
  
  function logout(){
    try{
      // Clear any stored tokens
      sessionStorage.removeItem('userToken')
      localStorage.removeItem('access_token')
      // Best-effort cookie clears (non-HttpOnly only)
      document.cookie = 'pit_access_token=; Max-Age=0; path=/;'
      document.cookie = 'access_token=; Max-Age=0; path=/'
    }catch(_){ /* ignore */ }
    navigate('/login', { replace:true })
  }

  useEffect(() => {
    if(loading) return
    ;(async () => {
      try{
        if(!token){ setFavs([]); return }
        // Switch to /user/favorites for robustness
        const res = await fetch('/user/favorites', { headers: { 'Authorization': `Bearer ${token}` } })
        if(!res.ok) { setFavs([]); return }
        const data = await res.json()
        setFavs(Array.isArray(data) ? data : [])
      }catch(_){ setFavs([]) }
    })()
  }, [loading, token])

  useEffect(() => {
    // When favorites list changes, fetch figure details for nicer display
    (async () => {
      try{
        const slugs = Array.isArray(favs) ? favs.map(f=>f.figure_slug) : []
        const uniq = Array.from(new Set(slugs))
        const out = []
        await Promise.all(uniq.map(async (slug) => {
          try{
            const r = await fetch(`/figures/${encodeURIComponent(slug)}`)
            if(r.ok){
              const d = await r.json()
              out.push({ slug, name: d.name || slug, image_url: d.image_url || null })
            }else{
              out.push({ slug, name: slug, image_url: null })
            }
          }catch(_){ out.push({ slug, name: slug, image_url: null }) }
        }))
        setFavDetails(out)
      }catch(_){ /* ignore */ }
    })()
  }, [favs])

  async function startWith(slug){
    if(!user) return navigate('/login')
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
        body: JSON.stringify({ user_id: user.id, title: 'New thread', figure_slug: slug })
      })
      if(!res.ok) throw new Error(await res.text())
      const data = await res.json()
      const id = data.thread_id || data.id
      navigate(`/thread/${id}`)
    }catch(e){ setErr(e.message || 'Failed to start thread') }
    finally{ setCreating(false) }
  }

  const modes = [
    { key: 'Young Learner', label: 'Young Learner (5–11)' },
    { key: 'Young Adult', label: 'Young Adult (11–16)' },
    { key: 'Student', label: 'Student (16–21)' },
    { key: 'Master', label: 'Master' },
  ]

  return (
    <div className="wrap" style={{maxWidth:1120}}>
  <LogoCard wide />
      <div className="banner" style={{margin:'8px 0', justifyContent:'space-between'}}>
        <div className="brand-title">
          <h1 style={{margin:0,fontSize:'var(--fs-xl)'}}>Welcome back{user?.username ? `, ${user.username}` : ''} 👋</h1>
          <div className="muted" style={{fontSize:'var(--fs-sm)'}}>{loading ? 'Loading your profile…' : 'Your personalized dashboard'}</div>
        </div>
        <div className="banner-actions" style={{gap:12}}>
          <button
            className="btn btn-primary"
            disabled={creating || !user}
            onClick={() => navigate('/figures')}
          >Start Conversation</button>
          <button className="btn" onClick={() => navigate('/threads')}>View Threads</button>
          <button className="btn" onClick={logout}>Logout</button>
        </div>
      </div>

      {err ? <div className="muted" style={{color:'#fca5a5', marginBottom:12}}>{err}</div> : null}

      <div style={{display:'grid', gridTemplateColumns:'1fr 360px', gap:20}}>
        <div className="stack">
          <div className="card panel" style={{padding:20}}>
            <h2 style={{margin:'0 0 12px', fontSize:'var(--fs-lg)'}}>Quick Start</h2>
            {favDetails.length === 0 ? (
              <div className="muted" style={{padding:4}}>
                No favorites yet. Browse figures to add some.
                <div style={{marginTop:12}}>
                  <button className="btn btn-primary sm" onClick={()=>navigate('/figures')} disabled={creating}>Browse Figures →</button>
                </div>
              </div>
            ) : (
              <div style={{display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(240px, 1fr))', gap:14}}>
                {favDetails.map(fd => (
                  <div key={fd.slug} className="card" style={{padding:14, display:'flex', flexDirection:'column', gap:10}}>
                    <div style={{display:'flex', alignItems:'center', gap:12}}>
                      {fd.image_url ? (
                        <img src={fd.image_url} alt={fd.name} style={{width:56, height:56, borderRadius:16, objectFit:'cover', border:'1px solid rgba(255,255,255,.12)'}} />
                      ) : (
                        <div style={{width:56, height:56, borderRadius:16, background:'#0a1228', border:'1px solid rgba(255,255,255,.12)', display:'flex',alignItems:'center',justifyContent:'center'}}>
                          <img src="/static/logo.png" alt="" style={{width:'80%',height:'80%',objectFit:'contain',opacity:.85}} />
                        </div>
                      )}
                      <div style={{flex:1}}>
                        <div style={{fontWeight:600, fontSize:'0.95rem'}}>{fd.name}</div>
                        <div className="muted" style={{fontSize:'0.75rem'}}>{fd.slug}</div>
                      </div>
                    </div>
                    <div style={{display:'flex', justifyContent:'flex-start', gap:8}}>
                      <button className="btn btn-primary sm" onClick={()=>startWith(fd.slug)} disabled={creating}>Start</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="card panel" style={{padding:20}}>
            <h2 style={{margin:'0 0 12px', fontSize:'var(--fs-lg)'}}>History & Topics</h2>
            <div style={{display:'flex',flexWrap:'wrap',gap:10}}>
              {TOPICS.map(t => (
                <div key={t} style={{background:'rgba(148,163,184,.12)',padding:'8px 12px',borderRadius:'var(--radius-md)',fontSize:'var(--fs-sm)',color:'var(--text)'}}>{t}</div>
              ))}
            </div>
          </div>
        </div>
        <aside className="stack" style={{gap:20}}>
          <div className="card panel" style={{padding:20}}>
            <h2 style={{margin:'0 0 12px', fontSize:'var(--fs-lg)'}}>Interaction Style</h2>
            <p className="muted" style={{marginTop:0,fontSize:'var(--fs-sm)'}}>Choose how the assistant should speak to you.</p>
            <div className="stack" style={{gap:8}}>
              {modes.map(m => (
                <button
                  key={m.key}
                  onClick={() => setMode(m.key)}
                  className={mode === m.key ? 'btn btn-primary' : 'btn'}
                  style={{textAlign:'left', display:'flex', flexDirection:'column'}}
                >
                  <span style={{fontWeight:600}}>{m.label}</span>
                  {mode === m.key ? <small style={{color:'#9cf'}}>Selected</small> : null}
                </button>
              ))}
            </div>
            <div style={{marginTop:12}} className="muted">Current: <strong>{mode}</strong></div>
          </div>
        </aside>
      </div>

      <style>{`@media (max-width: 900px) { div[style*='grid-template-columns']{ grid-template-columns:1fr !important; } }`}</style>
    </div>
  )
}
