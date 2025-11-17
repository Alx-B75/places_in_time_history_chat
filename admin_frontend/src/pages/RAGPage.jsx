import React, { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

async function api(path, opts={}){
  const res = await fetch(path, { headers: { 'Content-Type':'application/json', ...(opts.headers||{}) }, ...opts })
  if(res.status === 204) return { ok:true, status:204 }
  const data = await res.json().catch(()=>({}))
  if(!res.ok) throw new Error(data?.detail || res.statusText || 'Request failed')
  return data
}

export default function RAGPage(){
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [contexts, setContexts] = useState([])
  const [ctxLoading, setCtxLoading] = useState(false)
  const [form, setForm] = useState({ source_name:'', content_type:'bio', source_url:'', content:'' })
  const [params, setParams] = useSearchParams()
  const selectedSlug = params.get('slug') || ''

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        setLoading(true)
        const s = await api('/admin/rag/sources')
        if(cancelled) return
        setSummary(s)
      } catch(e){ if(!cancelled) setError(e.message||'Failed to load RAG summary') }
      finally { if(!cancelled) setLoading(false) }
    })()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if(!selectedSlug) { setContexts([]); return }
    let cancelled = false
    ;(async () => {
      try{
        setCtxLoading(true)
        const rows = await api(`/admin/rag/contexts?figure_slug=${encodeURIComponent(selectedSlug)}`)
        if(cancelled) return
        setContexts(Array.isArray(rows) ? rows : [])
      }catch(e){ if(!cancelled) setError(e.message||'Failed to load contexts') }
      finally{ if(!cancelled) setCtxLoading(false) }
    })()
    return () => { cancelled = true }
  }, [selectedSlug])

  const figureList = useMemo(() => {
    const arr = summary?.figures || []
    return arr.slice().sort((a,b) => (a.name||a.slug||'').localeCompare(b.name||b.slug||''))
  }, [summary])

  async function addContext(e){
    e.preventDefault()
    if(!selectedSlug) return
    try{
      const payload = { figure_slug:selectedSlug, ...form }
      await api('/admin/rag/sources', { method:'POST', body: JSON.stringify(payload) })
      setForm({ source_name:'', content_type:'bio', source_url:'', content:'' })
      const rows = await api(`/admin/rag/contexts?figure_slug=${encodeURIComponent(selectedSlug)}`)
      setContexts(rows)
    }catch(e){ setError(e.message||'Failed to add context') }
  }

  async function updateContext(id, patch){
    try{
      await api(`/admin/rag/contexts/${id}`, { method:'PATCH', body: JSON.stringify(patch) })
      const rows = await api(`/admin/rag/contexts?figure_slug=${encodeURIComponent(selectedSlug)}`)
      setContexts(rows)
    }catch(e){ setError(e.message||'Failed to update context') }
  }

  async function deleteContext(id){
    try{
      await api(`/admin/rag/contexts/${id}`, { method:'DELETE' })
      setContexts(contexts.filter(c=>c.id!==id))
    }catch(e){ setError(e.message||'Failed to delete context') }
  }

  return (
    <div className="stack" style={{gap:12}}>
      <div className="card panel" style={{padding:16}}>
        <h3 style={{margin:'0 0 8px'}}>RAG Collection</h3>
        {loading ? <div>Loading…</div> : null}
        {error ? <div style={{color:'#fca5a5'}}>{error}</div> : null}
        {summary && (
          <div className="muted" style={{display:'flex', gap:16, flexWrap:'wrap'}}>
            <div><strong>Status:</strong> {summary.collection.ok ? 'OK' : 'Error'}</div>
            {summary.collection.name ? <div><strong>Name:</strong> {summary.collection.name}</div> : null}
            {summary.collection.doc_count!=null ? <div><strong>Docs:</strong> {summary.collection.doc_count}</div> : null}
            {summary.collection.detail ? <div><strong>Detail:</strong> {summary.collection.detail}</div> : null}
          </div>
        )}
      </div>

      <div className="card panel" style={{padding:16}}>
        <h3 style={{margin:'0 0 8px'}}>Figures</h3>
        <div style={{display:'grid', gridTemplateColumns:'260px 1fr', gap:16}}>
          <div style={{borderRight:'1px solid var(--border)', paddingRight:12}}>
            <div className="stack" style={{gap:8, maxHeight:420, overflow:'auto'}}>
              {figureList.map(f => (
                <button
                  key={f.slug}
                  className={selectedSlug === f.slug ? 'btn btn-primary' : 'btn'}
                  onClick={() => setParams({ slug: f.slug })}
                  style={{display:'flex', justifyContent:'space-between'}}
                >
                  <span>{f.name || f.slug}</span>
                  <span className="muted" style={{fontSize:'.8rem'}}>ctx: {f.total_contexts}</span>
                </button>
              ))}
            </div>
          </div>
          <div>
            {!selectedSlug ? (
              <div className="muted">Select a figure to view and edit contexts</div>
            ) : (
              <div className="stack" style={{gap:12}}>
                <div style={{display:'flex', alignItems:'center', justifyContent:'space-between'}}>
                  <h4 style={{margin:0}}>Contexts for {selectedSlug}</h4>
                  {ctxLoading ? <span className="muted">Loading…</span> : null}
                </div>
                <div className="stack" style={{gap:8}}>
                  {contexts.length === 0 ? (
                    <div className="muted">No contexts yet.</div>
                  ) : contexts.map(c => (
                    <div key={c.id} className="card" style={{padding:12, border:'1px solid var(--border)', borderRadius:12}}>
                      <div style={{display:'flex', gap:12, alignItems:'baseline'}}>
                        <strong style={{minWidth:120}}>{c.source_name || '(unnamed)'}</strong>
                        <span className="muted">[{c.content_type || 'unknown'}]</span>
                      </div>
                      {c.source_url ? <div style={{marginTop:6}}><a href={c.source_url} target="_blank" rel="noreferrer">{c.source_url}</a></div> : null}
                      {c.content ? <pre style={{whiteSpace:'pre-wrap', marginTop:6, background:'#06111a', padding:8, borderRadius:8, maxHeight:200, overflow:'auto'}}>{c.content}</pre> : null}
                      <div style={{display:'flex', gap:8, marginTop:8}}>
                        <button className="btn sm" onClick={()=>updateContext(c.id, { is_manual: c.is_manual ? 0 : 1 })}>{c.is_manual ? 'Unset Manual' : 'Set Manual'}</button>
                        <button className="btn sm" onClick={()=>deleteContext(c.id)}>Delete</button>
                      </div>
                    </div>
                  ))}
                </div>
                <form onSubmit={addContext} className="card" style={{padding:12, border:'1px solid var(--border)', borderRadius:12}}>
                  <h4 style={{margin:'0 0 8px'}}>Add Manual Context</h4>
                  <div className="form-row">
                    <label>Source Name</label>
                    <input value={form.source_name} onChange={e=>setForm({...form, source_name:e.target.value})} required />
                  </div>
                  <div className="form-row">
                    <label>Content Type</label>
                    <input value={form.content_type} onChange={e=>setForm({...form, content_type:e.target.value})} placeholder="e.g. bio, quote, article" required />
                  </div>
                  <div className="form-row">
                    <label>Source URL (optional)</label>
                    <input value={form.source_url} onChange={e=>setForm({...form, source_url:e.target.value})} />
                  </div>
                  <div className="form-row">
                    <label>Content (optional)</label>
                    <textarea rows={5} value={form.content} onChange={e=>setForm({...form, content:e.target.value})} />
                  </div>
                  <button className="btn btn-primary" type="submit">Add Context</button>
                </form>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
