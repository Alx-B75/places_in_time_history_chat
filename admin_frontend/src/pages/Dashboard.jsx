import React, { useState } from 'react'
import { useInteraction } from '../contexts/InteractionContext'
import { useAuth } from '../contexts/AuthContext.jsx'
import { useNavigate } from 'react-router-dom'

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
  const { user, loading } = useAuth()
  const { mode, setMode } = useInteraction()
  const navigate = useNavigate()
  const [creating, setCreating] = useState(false)
  const [err, setErr] = useState('')

  const modes = [
    { key: 'Young Learner', label: 'Young Learner (5–11)' },
    { key: 'Young Adult', label: 'Young Adult (11–16)' },
    { key: 'Student', label: 'Student (16–21)' },
    { key: 'Master', label: 'Master' },
  ]

  return (
    <div style={{padding:12, maxWidth:980, margin:'0 auto'}}>
      <header style={{marginBottom:18}}>
        <h1 style={{margin:0,fontSize:'1.8rem'}}>Welcome back{user?.username ? `, ${user.username}` : ''} 👋</h1>
        <p style={{color:'#666',marginTop:6}}>{loading ? 'Loading your profile…' : 'Your personalized dashboard'}</p>
      </header>

      <div style={{display:'grid',gridTemplateColumns:'1fr 320px',gap:16}}>
        <div>
          <SectionCard title="Your Figures">
            <div style={{padding:12,color:'#666'}}>No favorites yet — when you favorite figures they will appear here.</div>
          </SectionCard>

          <SectionCard title="History & Topics">
            <div style={{display:'flex',flexWrap:'wrap',gap:8}}>
              {TOPICS.map(t => (
                <div key={t} style={{background:'#f7f9fc',padding:'8px 12px',borderRadius:8}}>{t}</div>
              ))}
            </div>
          </SectionCard>
        </div>

        <aside>
          <SectionCard title="Interaction Style">
            <p style={{color:'#666',marginTop:0}}>Choose how the assistant should speak to you.</p>
            <div style={{display:'flex',flexDirection:'column',gap:8}}>
              {modes.map(m => (
                <button
                  key={m.key}
                  onClick={() => setMode(m.key)}
                  className={mode === m.key ? 'btn btn-primary' : 'btn'}
                  style={{textAlign:'left'}}
                >
                  <div style={{fontWeight:600}}>{m.label}</div>
                  {mode === m.key ? <small style={{color:'#9cf'}}> Selected</small> : null}
                </button>
              ))}
            </div>

            <div style={{marginTop:12,color:'#666'}}>Current: <strong>{mode}</strong></div>
          </SectionCard>

          <SectionCard title="Quick Actions">
            {err ? <div style={{color:'crimson', marginBottom:8}}>{err}</div> : null}
            <div style={{display:'flex',flexDirection:'column',gap:8}}>
              <button
                className="btn btn-primary"
                disabled={creating || !user}
                onClick={async () => {
                  if(!user) return
                  setErr('')
                  setCreating(true)
                  try{
                    const token = sessionStorage.getItem('userToken') || localStorage.getItem('access_token')
                    const res = await fetch('/threads', {
                      method: 'POST',
                      headers: {
                        'Content-Type': 'application/json',
                        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                      },
                      body: JSON.stringify({ user_id: user.id, title: 'New thread' })
                    })
                    if(!res.ok) throw new Error(await res.text())
                    const data = await res.json()
                    const newId = data.thread_id || data.id
                    navigate(`/thread/${newId}`)
                  }catch(e){ setErr(e.message || 'Failed to create thread') }
                  finally{ setCreating(false) }
                }}
              >{creating ? 'Creating…' : 'Start a new conversation'}</button>
              <button className="btn" onClick={() => navigate('/threads')}>View saved threads</button>
            </div>
          </SectionCard>
        </aside>
      </div>

      <style>{`
        @media (max-width: 800px) {
          div[style*="gridTemplateColumns"]{ grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  )
}
