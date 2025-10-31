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
  if(!token){
    // redirect unauthenticated users to a safe public page
    return <Navigate to="/guest/guy-fawkes" replace />
  }
  // Optional normalization: ensure sessionStorage has a value for other code that
  // reads sessionStorage.userToken. We avoid overwriting an existing session value.
  try{
    if(!sessionStorage.getItem('userToken') && localStorage.getItem('access_token')){
      sessionStorage.setItem('userToken', localStorage.getItem('access_token'))
    }
  }catch(_){ /* ignore storage permission errors */ }

  return children
}
