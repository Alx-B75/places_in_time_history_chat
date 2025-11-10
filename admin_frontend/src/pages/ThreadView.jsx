import React, { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext.jsx'

export default function ThreadView(){
  const { id } = useParams()
  const threadId = useMemo(() => parseInt(id, 10), [id])
  const location = useLocation()
  const fromGuestUpgrade = location.state && location.state.fromGuestUpgrade === true
  const { user, loading } = useAuth()
  const [messages, setMessages] = useState([])
  const [text, setText] = useState('')
  const [figure, setFigure] = useState('')
  const [err, setErr] = useState('')
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleInput, setTitleInput] = useState('')
  const [figures, setFigures] = useState([])
  const [sending, setSending] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    if(loading || !user || !threadId) return
    ;(async () => {
      try{
        const token = sessionStorage.getItem('userToken') || localStorage.getItem('access_token')
        const [threadRes, msgsRes, figsRes] = await Promise.all([
          fetch(`/threads/${threadId}`, { headers: token ? { 'Authorization': `Bearer ${token}` } : {} }),
          fetch(`/threads/${threadId}/messages`, { headers: token ? { 'Authorization': `Bearer ${token}` } : {} }),
          fetch('/figures')
        ])
        if(threadRes.ok){
          const thread = await threadRes.json()
          setTitleInput(thread.title || `Thread #${threadId}`)
        }
        if(!msgsRes.ok) throw new Error(await msgsRes.text())
        const msgs = await msgsRes.json()
        setMessages(msgs || [])
        if(figsRes.ok){
          const list = await figsRes.json()
          setFigures(list || [])
        }
      }catch(e){ setErr(e.message || 'Failed to load thread') }
    })()
  }, [loading, user, threadId])

  async function send(e){
    e.preventDefault()
    setErr('')
    if(!text.trim() || sending) return
    try{
      setSending(true)
      const payload = {
        user_id: user.id,
        thread_id: threadId,
        figure_slug: figure || undefined,
        message: text
        // model_used intentionally omitted to allow backend llm_config to decide.
      }
      const token = sessionStorage.getItem('userToken') || localStorage.getItem('access_token')
      const res = await fetch('/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify(payload)
      })
      if(!res.ok) throw new Error(await res.text())
      // After a successful /ask, re-fetch the authoritative history to avoid duplicates
      const msgsRes = await fetch(`/threads/${threadId}/messages`, { headers: token ? { 'Authorization': `Bearer ${token}` } : {} })
      if(!msgsRes.ok) throw new Error(await msgsRes.text())
      const fresh = await msgsRes.json()
      setMessages(fresh || [])
      setText('')
    }catch(e){ setErr(e.message || 'Ask failed') }
    finally{ setSending(false) }
  }

  if(loading) return <div style={{padding:24}}>Loading…</div>
  if(!user) return <div style={{padding:24}}>Please log in.</div>

  return (
    <div style={{padding:16, maxWidth:900, margin:'0 auto'}}>
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:8,flexWrap:'wrap'}}>
        <div style={{display:'flex',alignItems:'center',gap:8}}>
          <button
            className="btn"
            onClick={() => {
              if(fromGuestUpgrade){
                navigate('/dashboard', { replace: true })
              }else{
                navigate(-1)
              }
            }}
          >← Back</button>
        </div>
        <div style={{display:'flex',alignItems:'center',gap:8}}>
          {editingTitle ? (
            <form onSubmit={async (e) => {
              e.preventDefault()
              setErr('')
              try{
                const token = sessionStorage.getItem('userToken') || localStorage.getItem('access_token')
                const res = await fetch(`/threads/${threadId}/title`, {
                  method: 'PATCH',
                  headers: {
                    'Content-Type': 'application/json',
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                  },
                  body: JSON.stringify({ title: titleInput })
                })
                if(!res.ok) throw new Error(await res.text())
              }catch(e){ setErr(e.message || 'Rename failed') }
              finally{ setEditingTitle(false) }
            }} style={{display:'flex',gap:8}}>
              <input value={titleInput} onChange={e=>setTitleInput(e.target.value)} style={{padding:'6px 10px'}} />
              <button className="btn btn-primary" type="submit">Save</button>
              <button className="btn" type="button" onClick={()=>{setEditingTitle(false)}}>Cancel</button>
            </form>
          ) : (
            <h2 style={{margin:'8px 0',display:'flex',alignItems:'center',gap:12}}>
              {titleInput || `Thread #${threadId}`}
              <button className="btn" type="button" onClick={()=>setEditingTitle(true)} style={{fontSize:12,padding:'4px 8px'}}>Rename</button>
            </h2>
          )}
        </div>
        <span style={{flexGrow:1}} />
      </div>
      {err ? <div style={{color:'crimson'}}>{err}</div> : null}
      <div style={{border:'1px solid #eee',borderRadius:8,padding:12,minHeight:240,marginBottom:12}}>
        {messages.length === 0 ? <div style={{color:'#666'}}>No messages yet.</div> : (
          <div style={{display:'flex',flexDirection:'column',gap:8}}>
            {messages.map((m,i) => (
              <div key={i} style={{alignSelf: m.role==='user' ? 'flex-end' : 'flex-start', maxWidth:'75%'}}>
                <div style={{fontSize:12,color:'#888'}}>{m.role}</div>
                <div style={{background: m.role==='user' ? '#e8f0ff' : '#f6f6f6', padding:10, borderRadius:10}}>{m.message}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <form onSubmit={send} style={{display:'flex',gap:8,alignItems:'center'}}>
        <select value={figure} onChange={e=>setFigure(e.target.value)}>
          <option value="">No figure</option>
          {figures.map(f => <option key={f.slug} value={f.slug}>{f.name}</option>)}
        </select>
        <input style={{flex:1}} value={text} onChange={e=>setText(e.target.value)} placeholder="Type your message" disabled={sending} />
        <button className="btn btn-primary" type="submit" disabled={sending}>{sending ? 'Sending…' : 'Send'}</button>
      </form>
    </div>
  )
}
