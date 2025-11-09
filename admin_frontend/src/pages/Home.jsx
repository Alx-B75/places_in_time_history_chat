import React, { useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext.jsx'

export default function Home(){
  const { user } = useAuth()
  const navigate = useNavigate()

  // If already authenticated, steer to dashboard automatically
  useEffect(() => {
    const token = sessionStorage.getItem('userToken') || localStorage.getItem('access_token')
    if(token){ navigate('/dashboard', { replace: true }) }
  }, [])
  return (
    <div style={{padding:24}}>
      <h1>Welcome</h1>
    <p>This is a neutral start page. Choose an action:</p>
      <ul>
        <li><Link to="/dashboard">Go to your Dashboard</Link></li>
        <li>Or open a guest chat by visiting /guest/:slug</li>
      </ul>
    </div>
  )
}
