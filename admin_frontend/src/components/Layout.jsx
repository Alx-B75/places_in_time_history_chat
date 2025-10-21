import React from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'

export default function Layout() {
  const loc = useLocation()
  const title = loc.pathname.split('/').pop() || 'llm'
  function logout(){
    sessionStorage.removeItem('adminToken')
    window.location.href = '/admin/ui#/login'
  }
  return (
    <div className="app">
      <aside className="sidebar">
        <h2>Admin</h2>
        <nav>
          <ul>
            <li><Link to="/admin/llm">LLM</Link></li>
            <li><Link to="/admin/figures">Figures</Link></li>
            <li><Link to="/admin/rag">RAG</Link></li>
            <li><Link to="/admin/ab">A/B</Link></li>
            <li><button onClick={logout}>Logout</button></li>
          </ul>
        </nav>
      </aside>
      <main className="main">
        <header><h1>{title.toUpperCase()}</h1></header>
        <section className="content"><Outlet /></section>
      </main>
    </div>
  )
}
