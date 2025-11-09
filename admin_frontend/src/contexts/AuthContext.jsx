import React, { createContext, useContext, useEffect, useMemo, useState, useRef } from 'react'

function readCookie(name){
  try{
    const m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]+)'))
    return m ? decodeURIComponent(m[1]) : null
  }catch(_){ return null }
}

export const AuthContext = createContext(null)

export function AuthProvider({ children }){
  const [token, setToken] = useState(null)
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const initTried = useRef(false)

  // Discover token from multiple places (sessionStorage, localStorage, dev cookie)
  useEffect(() => {
    // Attempt initial discovery only once; if login page sets storage slightly AFTER mount,
    // we re-check after a short delay to catch race conditions.
    if(initTried.current) return
    initTried.current = true
    function discover(){
      try{
        const t = sessionStorage.getItem('userToken')
          || localStorage.getItem('access_token')
          || localStorage.getItem('user_token')
          || readCookie('pit_access_token')
          || readCookie('access_token')
        if(t) setToken(prev => prev || t)
      }catch(_){ /* ignore */ }
      setLoading(false)
    }
    discover()
    // second pass after 150ms to capture freshly written sessionStorage from redirect
    const id = setTimeout(discover, 150)
    return () => clearTimeout(id)
  }, [])

  // Fetch /auth/me when we have a token
  useEffect(() => {
    let cancelled = false
    async function run(){
      if(!token) { setUser(null); return }
      try{
        setLoading(true)
        const res = await fetch('/auth/me', { headers: { 'Authorization': `Bearer ${token}` } })
        if(!res.ok){ throw new Error(await res.text()) }
        const data = await res.json()
        if(cancelled) return
        setUser({ id: data.user_id, username: data.username, role: data.role })
        // normalize so other code can find it
        try{ if(!sessionStorage.getItem('userToken')) sessionStorage.setItem('userToken', token) }catch(_){}
      }catch(e){ if(!cancelled){ setError(e.message||'auth'); setUser(null) } }
      finally{ if(!cancelled) setLoading(false) }
    }
    run()
    return () => { cancelled = true }
  }, [token])

  // Provide an explicit refresh method so login page can force /auth/me fetch post-navigation
  async function refresh(){
    if(!token) return
    try{
      setLoading(true)
      const res = await fetch('/auth/me', { headers: { 'Authorization': `Bearer ${token}` } })
      if(!res.ok) return
      const data = await res.json()
      setUser({ id: data.user_id, username: data.username, role: data.role })
    }finally{ setLoading(false) }
  }

  const value = useMemo(() => ({ token, setToken, user, setUser, loading, error, refresh }), [token, user, loading, error])

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(){
  const ctx = useContext(AuthContext)
  if(!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
