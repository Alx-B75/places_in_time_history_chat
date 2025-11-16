import React, { useEffect, useState } from 'react'

export default function RAGPage(){
  const [figures, setFigures] = useState([])
  const [err, setErr] = useState(null)

  useEffect(()=>{
    ;(async ()=>{
      try{
        const token = sessionStorage.getItem('adminToken') || sessionStorage.getItem('userToken') || localStorage.getItem('access_token')
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {}
        const res = await fetch('/admin/rag/sources', { headers })
        if(!res.ok) throw new Error(await res.text())
        const data = await res.json()
        setFigures(Array.isArray(data?.figures) ? data.figures : [])
      }catch(e){ setErr(e.message || 'Failed to load RAG summary') }
    })()
  }, [])

  return (
    <div>
      <h2>RAG (Retrieval-Augmented Generation)</h2>
      <p>Per-figure ingestion & context management. Click a slug to open the per-figure ingestion UI (drag & drop).</p>
      {err ? <div style={{color:'var(--danger)'}}>{err}</div> : null}
      <table style={{width:'100%',borderCollapse:'collapse'}}>
        <thead><tr><th>Slug</th><th>Name</th><th>Contexts</th></tr></thead>
        <tbody>
          {figures.map(f=> (
            <tr key={f.slug}>
              <td><a href={`/admin/figure_rag.html?slug=${encodeURIComponent(f.slug)}`}>{f.slug}</a></td>
              <td>{f.name}</td>
              <td>{f.total_contexts ?? 0}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>If the table is empty you may need to <em>Step Up</em> to an admin account in the admin UI to view RAG data.</p>
    </div>
  )
}
