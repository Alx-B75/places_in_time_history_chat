import React from 'react'
import { Link } from 'react-router-dom'
import { asset } from '../lib/assetBase.js'

export default function LogoCard({ size=140, style, to='/dashboard', wide=false }){
  const card = (
    <div
      className={`card panel logo-card${wide ? ' wide' : ''}`}
      style={{
        margin:'16px 0',
        display:'flex',
        justifyContent:'center',
        alignItems:'center',
        padding:'18px',
        background:'#0f172a',
        border:'1px solid rgba(255,255,255,.06)',
        borderRadius:14,
        boxShadow:'0 12px 24px rgba(0,0,0,.35)',
        cursor: to ? 'pointer' : 'default',
        width: wide ? '100%' : undefined,
        maxWidth: wide ? '100%' : undefined,
        ...style
      }}
    >
      <div className="brand-mark" aria-hidden style={{width:size, height:size, borderRadius:24, overflow:'hidden'}}>
        <img src={asset('/static/logo.png')} alt="Places in Time" style={{width:'100%',height:'100%',objectFit:'cover',borderRadius:'inherit'}} onError={(e)=>{ e.currentTarget.src = asset('/static/pit-favicon-mark.ico'); }} />
      </div>
    </div>
  )

  return to ? <Link to={to} style={{textDecoration:'none'}} aria-label="Back to dashboard">{card}</Link> : card
}
