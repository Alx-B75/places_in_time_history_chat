import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function FiguresPage(){
  const [figures, setFigures] = useState([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try{
        setLoading(true)
        const res = await fetch('/figures/?limit=500')
        if(!res.ok) throw new Error(await res.text())
        const data = await res.json()
        if(cancelled) return
        setFigures(Array.isArray(data) ? data : [])
      }catch(e){ if(!cancelled) setError(e.message || 'Failed to load figures') }
      finally{ if(!cancelled) setLoading(false) }
    })()
    return () => { cancelled = true }
  }, [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    const arr = figures.slice().sort((a,b) => (a.name||'').localeCompare(b.name||''))
    if(!q) return arr
    return arr.filter(f => (f.name||'').toLowerCase().includes(q) || (f.slug||'').toLowerCase().includes(q))
  }, [figures, query])

  return (
    <div className="card panel" style={{padding:16}}>
      <div style={{display:'flex', alignItems:'center', gap:12, marginBottom:12}}>
        <input
          type="text"
          className="pit-input"
          placeholder="Search figures by name or slug…"
          value={query}
          onChange={e=>setQuery(e.target.value)}
          style={{flex:1, padding:'10px 12px', borderRadius:12, border:'1px solid var(--border)', background:'#0a1820', color:'var(--text)'}}
        />
      </div>
      {loading ? <div>Loading…</div> : null}
      {error ? <div style={{color:'#fca5a5'}}>{error}</div> : null}
      <div style={{display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(280px, 1fr))', gap:12}}>
        {filtered.map(f => (
          <div key={f.slug} className="card" style={{padding:12, display:'flex', gap:10, alignItems:'center'}}>
            {f.image_url ? (
              <img src={f.image_url} alt={f.name} style={{width:56,height:56,borderRadius:12,objectFit:'cover',border:'1px solid rgba(255,255,255,.12)'}} />
            ) : (
              <div style={{width:56,height:56,borderRadius:12,background:'#0a1228',border:'1px solid rgba(255,255,255,.12)',display:'flex',alignItems:'center',justifyContent:'center'}}>
                <img src="/logo.svg" alt="" style={{width:'80%',height:'80%',objectFit:'contain',opacity:.85}} />
              </div>
            )}
            <div style={{flex:1}}>
              <div style={{fontWeight:600}}>{f.name}</div>
              <div className="muted" style={{fontSize:'.85rem'}}>{f.slug}</div>
            </div>
            <div style={{display:'flex',gap:8}}>
              <button className="btn sm" onClick={()=>navigate(`/admin/rag?slug=${encodeURIComponent(f.slug)}`)}>Manage RAG</button>
              <a className="btn sm" href={`/static/admin_figure_edit.html?slug=${encodeURIComponent(f.slug)}`} target="_blank" rel="noreferrer">Edit</a>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
