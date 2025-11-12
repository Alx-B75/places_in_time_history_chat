import React, { useEffect, useMemo, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext.jsx'
import LogoCard from '../components/LogoCard.jsx'

export default function FigureSelect(){
  const { user, loading } = useAuth()
  const [figures, setFigures] = useState([])
  const [query, setQuery] = useState('')
  const [err, setErr] = useState('')
  const [creating, setCreating] = useState(false)
  const [favs, setFavs] = useState(new Set())
  const navigate = useNavigate()
  const [favLoading, setFavLoading] = useState(null) // slug currently toggling
  const [toast, setToast] = useState(null)
  const toastTimer = useRef(null)

  useEffect(() => {
    if(loading) return
    ;(async () => {
      try{
        const res = await fetch('/figures/?limit=500')
        if(!res.ok) throw new Error(await res.text())
        const data = await res.json()
        setFigures(Array.isArray(data) ? data : [])
      }catch(e){ setErr(e.message || 'Failed to load figures') }
    })()
  }, [loading])

  // Load user favorites
  useEffect(() => {
    if(loading) return
    ;(async () => {
      try{
        const token = sessionStorage.getItem('userToken') || localStorage.getItem('access_token')
        if(!token) return
        // Prefer the stable /user/favorites path
        const res = await fetch('/user/favorites', { headers: { 'Authorization': `Bearer ${token}` } })
        if(!res.ok) return
        const data = await res.json()
        const slugs = Array.isArray(data) ? data.map(f=>f.figure_slug) : []
        setFavs(new Set(slugs))
      }catch(_){ /* ignore */ }
    })()
  }, [loading])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    const arr = figures.slice().sort((a,b) => (a.name||'').localeCompare(b.name||''))
    if(!q) return arr
    return arr.filter(f => (f.name||'').toLowerCase().includes(q) || (f.slug||'').toLowerCase().includes(q))
  }, [figures, query])

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

  function showToast(msg){
    setToast(msg)
    if(toastTimer.current) clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(()=> setToast(null), 2500)
  }

  async function toggleFavorite(slug){
    if(favLoading) return
    setFavLoading(slug)
    try{
      const token = sessionStorage.getItem('userToken') || localStorage.getItem('access_token')
      if(!token){
        // Store locally as a hint, but real persistence requires login
        const copy = new Set(favs)
        copy.has(slug) ? copy.delete(slug) : copy.add(slug)
        setFavs(copy)
        showToast(copy.has(slug) ? 'Favorited (local only)' : 'Unfavorited (local only)')
        return
      }
      const isFav = favs.has(slug)
      // Use /user/favorites for reliability
      const res = await fetch(`/user/favorites/${encodeURIComponent(slug)}`, {
        method: isFav ? 'DELETE' : 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if(!res.ok && !(isFav && res.status===204)) throw new Error(await res.text())
      const next = new Set(favs)
      isFav ? next.delete(slug) : next.add(slug)
      setFavs(next)
      showToast(isFav ? 'Removed from favorites' : 'Added to favorites')
    }catch(e){ setErr(e.message || 'Failed to toggle favorite') }
    finally{ setFavLoading(null) }
  }

  return (
    <div className="wrap" style={{maxWidth:1120}}>
      <LogoCard wide />
      <div className="banner" style={{margin:'8px 0', justifyContent:'space-between'}}>
        <div className="brand-title">
          <h1 style={{margin:0}}>Choose a Figure</h1>
          <div className="muted">Pick a historical figure to start a conversation</div>
        </div>
        <div className="banner-actions">
          <button className="btn" onClick={()=>navigate('/dashboard')}>← Back</button>
        </div>
      </div>

      <div className="card panel" style={{padding:16, marginBottom:12}}>
        <input
          type="text"
          className="pit-input"
          placeholder="Search figures by name or slug…"
          value={query}
          onChange={e=>setQuery(e.target.value)}
          style={{width:'100%', padding:'10px 12px', borderRadius:12, border:'1px solid var(--border)', background:'#0a1820', color:'var(--text)'}}
        />
      </div>

      {err ? <div className="muted" style={{color:'#fca5a5', marginBottom:8}}>{err}</div> : null}

      <div className="fig-grid">
        {filtered.map(f => {
          const isFav = favs.has(f.slug)
          return (
          <div key={f.slug} className="fig-card">
            <div className="fig-card-head">
              {f.image_url ? (
                  <img className="fig-img" src={f.image_url} alt={f.name} />
                ) : <div className="fig-img" aria-hidden style={{display:'flex',alignItems:'center',justifyContent:'center',background:'#0a1228'}}>
                  <img src="/static/logo.png" alt="Logo" style={{width:'90%',height:'90%',objectFit:'contain',opacity:.85}} />
                </div>}
              <div className="fig-title">{f.name}</div>
            </div>
            <div className="fig-desc" style={{flex:1}}>{f.short_summary || `About ${f.name} (${f.slug})`}</div>
            <div className="fig-actions">
              <button disabled={creating} className="btn btn-primary sm" onClick={()=>startWith(f.slug)}>{creating ? 'Creating…' : 'Select'}</button>
              <button
                className={`btn sm fave-btn ${isFav ? 'active' : ''}`}
                aria-pressed={isFav}
                onClick={()=>toggleFavorite(f.slug)}
                disabled={!!favLoading}
                aria-busy={favLoading === f.slug}
              >{favLoading === f.slug ? '…' : (isFav ? '★ Favorited' : '☆ Favorite')}</button>
            </div>
          </div>
        )})}
      </div>

      {toast && (
        <div style={{position:'fixed',bottom:24,right:24,background:'rgba(0,0,0,.8)',color:'#fff',padding:'10px 14px',borderRadius:12,fontSize:'0.85rem',boxShadow:'0 4px 18px rgba(0,0,0,.35)',zIndex:1000}} role="status" aria-live="polite">{toast}</div>
      )}

      <style>{`
        .fig-grid{ display:grid; grid-template-columns: repeat( auto-fit, minmax(260px, 1fr) ); gap:12px; }
  .fig-card{ background:var(--card); border:1px solid var(--border); border-radius:14px; box-shadow:var(--shadow); padding:12px; display:flex; flex-direction:column; gap:8px; min-height:260px; }
        .fig-card-head{ display:flex; align-items:center; gap:10px; }
        .fig-img{ width:56px; height:56px; border-radius:14px; object-fit:cover; background:#0a1228; border:1px solid rgba(255,255,255,.12); }
        .fig-title{ font-weight:600; }
  .fig-desc{ color:var(--muted); font-size:.95rem; line-height:1.25; }
  .fig-actions{ display:flex; gap:8px; margin-top:auto; }
  .fave-btn{ background:linear-gradient(180deg,#c19d00,#a88000); color:#1a1200; border-color:#e8c454; }
  .fave-btn.active{ background:linear-gradient(180deg,#ffd24d,#e5b100); color:#1a1200; border-color:#ffe08a; }
  .fave-btn:hover{ border-color:#f9d86c; box-shadow:0 0 0 3px rgba(255,215,99,.25), var(--shadow); }
  .fave-btn[disabled]{ opacity:.55; cursor:not-allowed; }
      `}</style>
    </div>
  )
}
