import React from 'react'
import { Link } from 'react-router-dom'

export default function Home(){
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
