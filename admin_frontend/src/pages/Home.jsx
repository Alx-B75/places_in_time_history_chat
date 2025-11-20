import React, { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext.jsx'
import UserRegister from './UserRegister.jsx'

export default function Home(){
  const { token, user, loading } = useAuth()
  const navigate = useNavigate()

  // If already authenticated (same mechanism as dashboard), redirect to /dashboard.
  useEffect(() => {
    if(loading) return
    if(token || user){
      navigate('/dashboard', { replace: true })
    }
  }, [token, user, loading, navigate])

  // While auth is resolving, avoid flashing the form.
  if(loading){
    return <div className="wrap" style={{padding:24}}><p>Checking your session…</p></div>
  }

  // Unauthenticated visitors see the registration view by default.
  return <UserRegister />
}
