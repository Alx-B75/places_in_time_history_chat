import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext.jsx'
import LogoCard from '../components/LogoCard.jsx'

export default function ThreadView() {
  const { id } = useParams()
  const threadId = useMemo(() => parseInt(id, 10), [id])
  const location = useLocation()
  const fromGuestUpgrade = location.state && location.state.fromGuestUpgrade === true
  const navigate = useNavigate()
  const { user, loading } = useAuth()

  const [messages, setMessages] = useState([])
  const [text, setText] = useState('')
  // Figure selection removed for existing threads (will be used only at creation time)
  const [figures] = useState([])
  const [err, setErr] = useState('')
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleInput, setTitleInput] = useState('')
  const [sending, setSending] = useState(false)
  const [figure, setFigure] = useState(null)
  const [isFav, setIsFav] = useState(false)
  const [favBusy, setFavBusy] = useState(false)
  const [showSources, setShowSources] = useState(false)
  const [sources, setSources] = useState([])
  const inputRef = useRef(null)

  useEffect(() => {
    if (loading || !user || !threadId) return
    ; (async () => {
      try {
        const token = sessionStorage.getItem('userToken') || localStorage.getItem('access_token')
        const [threadRes, msgsRes] = await Promise.all([
          fetch(`/threads/${threadId}`, { headers: token ? { 'Authorization': `Bearer ${token}` } : {} }),
          fetch(`/threads/${threadId}/messages`, { headers: token ? { 'Authorization': `Bearer ${token}` } : {} })
        ])
        let figureSlug = null
        if (threadRes.ok) {
          const thread = await threadRes.json()
          setTitleInput(thread.title || `New thread`)
          figureSlug = thread.figure_slug || null
        }
        if (!msgsRes.ok) throw new Error(await msgsRes.text())
        const msgs = await msgsRes.json()
        setMessages(msgs || [])
        // collect sources from most recent assistant message with source_page metadata
        try {
          let last = null
          for (let i = msgs.length - 1; i >= 0; i--) {
            const m = msgs[i]
            if (m.role === 'assistant' && m.source_page) { last = m; break }
          }
          if (last) {
            const parsed = typeof last.source_page === 'string' ? JSON.parse(last.source_page) : (last.source_page || [])
            if (Array.isArray(parsed) && parsed.length) setSources(parsed)
            else setSources([])
          } else {
            setSources([])
          }
        } catch { setSources([]) }
        // fetch figure details for hero display
        if (figureSlug) {
          try{
            const f = await fetch(`/figures/${encodeURIComponent(figureSlug)}`)
            if (f.ok){ setFigure(await f.json()) }
          }catch(_){ /* ignore */ }
          // Load favorites to set current state
          try{
            const favRes = await fetch('/user/favorites', { headers: token ? { 'Authorization': `Bearer ${token}` } : {} })
            if(favRes.ok){
              const favs = await favRes.json()
              const slugs = Array.isArray(favs) ? favs.map(x=>x.figure_slug) : []
              setIsFav(slugs.includes(figureSlug))
            }
          }catch(_){ /* ignore */ }
        }
        // No figure list needed here; selection moved to creation flow.
      } catch (e) { setErr(e.message || 'Failed to load thread') }
    })()
  }, [loading, user, threadId])

  useEffect(() => {
    // autofocus compose area on load
    if(inputRef.current){ inputRef.current.focus() }
  }, [inputRef])

  async function send(e) {
    e.preventDefault()
    setErr('')
    if (!text.trim() || sending) return
    try {
      setSending(true)
      const payload = {
        user_id: user.id,
        thread_id: threadId,
  // figure_slug intentionally omitted in thread view updates.
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
      if (!res.ok) throw new Error(await res.text())
      const msgsRes = await fetch(`/threads/${threadId}/messages`, { headers: token ? { 'Authorization': `Bearer ${token}` } : {} })
      if (!msgsRes.ok) throw new Error(await msgsRes.text())
      const fresh = await msgsRes.json()
      setMessages(fresh || [])
      // update sources from latest assistant
      try {
        let last = null
        for (let i = fresh.length - 1; i >= 0; i--) {
          const m = fresh[i]
          if (m.role === 'assistant' && m.source_page) { last = m; break }
        }
        if (last) {
          const parsed = typeof last.source_page === 'string' ? JSON.parse(last.source_page) : (last.source_page || [])
          setSources(Array.isArray(parsed) ? parsed : [])
        } else setSources([])
      } catch { setSources([]) }
      setText('')
    } catch (e) { setErr(e.message || 'Ask failed') }
    finally { setSending(false) }
  }

  if (loading) return <div style={{ padding: 24 }}>Loading…</div>
  if (!user) return <div style={{ padding: 24 }}>Please log in.</div>

  return (
    <div className="wrap" style={{ maxWidth: 980 }}>
      <LogoCard wide />
      <div className="banner" style={{ margin: '8px 0', justifyContent:'space-between' }}>
        <div className="brand-title">
          <h1 style={{ margin: 0 }}>Conversation</h1>
          {/* Hide internal thread id from user */}
        </div>
        <div className="banner-actions">
          {editingTitle ? (
            <form onSubmit={async (e) => {
              e.preventDefault()
              setErr('')
              try {
                const token = sessionStorage.getItem('userToken') || localStorage.getItem('access_token')
                const res = await fetch(`/threads/${threadId}/title`, {
                  method: 'PATCH',
                  headers: {
                    'Content-Type': 'application/json',
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                  },
                  body: JSON.stringify({ title: titleInput })
                })
                if (!res.ok) throw new Error(await res.text())
              } catch (e) { setErr(e.message || 'Rename failed') }
              finally { setEditingTitle(false) }
            }} className="row">
              <input className="pit-input" value={titleInput} onChange={e => setTitleInput(e.target.value)} placeholder={`Thread #${threadId}`} />
              <button className="btn btn-primary" type="submit">Save</button>
              <button className="btn" type="button" onClick={() => { setEditingTitle(false) }}>Cancel</button>
            </form>
          ) : (
            <div className="row" style={{ gap: 12 }}>
              <button
                className="btn"
                onClick={() => {
                  if (fromGuestUpgrade) {
                    navigate('/dashboard', { replace: true })
                  } else {
                    navigate(-1)
                  }
                }}
              >← Back</button>
              <h2 style={{ margin: '8px 0' }}>{titleInput || `New thread`}</h2>
              <button className="btn btn-primary" type="button" onClick={() => setEditingTitle(true)} style={{ fontSize: 12, padding: '6px 10px' }}>Rename</button>
            </div>
          )}
        </div>
        <span style={{ flexGrow: 1 }} />
      </div>
      {err ? <div className="muted">{err}</div> : null}
      {/* Figure hero for consistency with guest page */}
      {figure ? (
        <div className="figure-hero card" style={{marginBottom:18, textAlign:'center'}}>
          <div className="figure-row" style={{alignItems:'center', justifyContent:'center', gap:18, flexDirection:'column'}}>
            {figure?.image_url ? (
              <img src={figure.image_url} alt={figure.name} className="avatar-lg" style={{border:'1px solid rgba(255,255,255,.18)'}} />
            ) : (
              <div className="avatar-lg" style={{background:'#0a1228',border:'1px solid rgba(255,255,255,.18)'}} />
            )}
            <div className="figure-hero-text" style={{maxWidth:760}}>
              <div className="figure-name-serif" style={{fontSize:'clamp(22px,3vw,32px)', fontWeight:700, textAlign:'center'}}>{figure?.name}</div>
              <div className="figure-desc-serif" style={{fontSize:'clamp(16px,2vw,20px)', textAlign:'center', marginTop:6}}>{figure?.short_summary}</div>
            </div>
            <div className="row" style={{gap:10, marginTop:6}}>
              <button
                className={`btn sm ${isFav ? 'btn-primary' : ''}`}
                onClick={async ()=>{
                  if(!figure) return
                  if(favBusy) return
                  setFavBusy(true)
                  try{
                    const token = sessionStorage.getItem('userToken') || localStorage.getItem('access_token')
                    if(!token) return
                    const method = isFav ? 'DELETE' : 'POST'
                    const res = await fetch(`/user/favorites/${encodeURIComponent(figure.slug)}`, { method, headers: { 'Authorization': `Bearer ${token}` }})
                    if(!res.ok && !(isFav && res.status===204)) throw new Error(await res.text())
                    setIsFav(!isFav)
                  }catch(e){ setErr(e.message || 'Favorite toggle failed') }
                  finally{ setFavBusy(false) }
                }}
                disabled={favBusy}
              >{isFav ? '★ Favorited' : '☆ Favorite'}</button>
            </div>
          </div>
        </div>
      ) : null}
      {!figure && (
        <div className="card panel" style={{marginBottom:18, padding:18, textAlign:'center'}}>
          <p className="muted" style={{margin:0}}>No figure selected. <button className="btn sm" onClick={()=>navigate('/figures')}>Choose a Figure</button></p>
        </div>
      )}
      <div className="card chat-card">
        <div className="messages">
          {messages.length === 0 ? <div className="muted">No messages yet.</div> : (
            messages.map((m, i) => (
              <div key={i} className={m.role === 'user' ? 'msg-user' : 'msg-assistant'}>{m.message}</div>
            ))
          )}
        </div>
        {/* Sources toggle footer */}
        {sources.length ? (
          <div style={{padding:'8px 12px', borderTop:'1px solid var(--border)', background:'rgba(148,163,184,.05)'}}>
            <button
              type="button"
              className="btn sm"
              onClick={()=> setShowSources(s => !s)}
              style={{minWidth:110}}
            >{showSources ? 'Hide Sources' : `Show Sources (${sources.length})`}</button>
            {showSources && (
              <div style={{marginTop:8,fontSize:13}}>
                {sources.map((s,idx)=>(
                  <div key={idx} style={{marginBottom:4}}>
                    • {s.source_url ? <a href={s.source_url} target="_blank" rel="noopener noreferrer">{s.source_name || `Source ${idx+1}`}</a> : (s.source_name || `Source ${idx+1}`)}
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : null}
        <form onSubmit={send} className="compose chat-input-row" style={{flexDirection:'column',alignItems:'stretch'}}>
          <textarea
            value={text}
            onChange={e => setText(e.target.value)}
            onKeyDown={e => { if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); send(e) } }}
            placeholder={figure ? `Ask ${figure.name} a question…` : 'Type your message (Enter to send, Shift+Enter for newline)'}
            disabled={sending}
            style={{width:'100%', boxSizing:'border-box'}}
            ref={inputRef}
          />
          <div style={{display:'flex',justifyContent:'flex-end'}}>
            <button className="send-btn" type="submit" disabled={sending}>{sending ? 'Sending…' : 'Send'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}
