import React from 'react'
import { Navigate } from 'react-router-dom'

// Simple route guard: checks for a `userToken` in sessionStorage.
// This is a stubbed auth check for now; replace with real auth logic later.
export default function RequireAuth({ children }){
  // Accept multiple token locations used across the project while auth is
  // being unified. Priority order:
  // 1. sessionStorage 'userToken'
  // 2. sessionStorage 'user_token'
  // 3. localStorage 'access_token'
  // 4. localStorage 'user_token'
  const token = sessionStorage.getItem('userToken') || sessionStorage.getItem('user_token') || localStorage.getItem('access_token') || localStorage.getItem('user_token') || null

  // Also accept a host-scoped cookie set by the static frontend during dev.
  // Cookies are host-scoped (not port-scoped), so this enables token sharing
  // between 127.0.0.1:8000 (backend) and 127.0.0.1:5173 (Vite dev server).
  function readCookie(name){
    try{
      const m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'))
      return m ? decodeURIComponent(m[2]) : null
    }catch(_){ return null }
  }
  const cookieToken = readCookie('pit_access_token') || readCookie('access_token') || readCookie('pit_access_token_localhost')
  const effectiveToken = token || cookieToken

  // Helpful debug logs (dev only) to diagnose why tokens may not be visible.
  try{
    if(window && window.location && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')){
      // eslint-disable-next-line no-console
      console.debug('[RequireAuth] token sources:', { sessionToken: sessionStorage.getItem('userToken'), localToken: localStorage.getItem('access_token'), cookieToken });
    }
  }catch(_){ }
  if(!effectiveToken){
    // redirect unauthenticated users to a safe public page
    return <Navigate to="/guest/guy-fawkes" replace />
  }
  // Optional normalization: ensure sessionStorage has a value for other code that
  // reads sessionStorage.userToken. We avoid overwriting an existing session value.
  try{
    if(!sessionStorage.getItem('userToken') && effectiveToken){
      sessionStorage.setItem('userToken', effectiveToken)
    }
  }catch(_){ /* ignore storage permission errors */ }

  return children
}
