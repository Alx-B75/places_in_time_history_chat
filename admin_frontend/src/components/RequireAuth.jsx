import React from 'react'
import { Navigate } from 'react-router-dom'

// Simple route guard: checks for a `userToken` in sessionStorage.
// This is a stubbed auth check for now; replace with real auth logic later.
export default function RequireAuth({ children }){
  const token = sessionStorage.getItem('userToken') || null
  if(!token){
    // redirect unauthenticated users to a safe public page
    return <Navigate to="/guest/guy-fawkes" replace />
  }
  return children
}
