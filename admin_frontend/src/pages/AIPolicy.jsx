import React from 'react'
import { Link } from 'react-router-dom'
import LogoCard from '../components/LogoCard.jsx'

export default function AIPolicy(){
  return (
    <div className="wrap" style={{maxWidth:860}}>
      <LogoCard wide to="/dashboard" />
      <div className="banner" style={{margin:'8px 0', justifyContent:'space-between'}}>
        <div className="brand-title">
          <h1 style={{margin:0}}>AI & Accuracy Policy</h1>
          <div className="muted">How AI is used and how we address accuracy</div>
        </div>
        <div className="banner-actions">
          <Link className="btn" to="/register">Back to Register</Link>
        </div>
      </div>
      <div className="card panel" style={{padding:22}}>
        <h2>1. Purpose</h2>
        <p>Places in Time blends historically verified sources with creative AI to provide engaging educational conversations. Our goal is to remain faithful to credible history while presenting content in a compelling, age-appropriate format.</p>

        <h2>2. Sources and grounding</h2>
        <ul>
          <li>Primary and secondary historical sources are curated into a knowledge base.</li>
          <li>Questions are answered using relevant excerpts (retrieval augmented generation) wherever possible.</li>
          <li>When an answer is speculative or outside verified context, the assistant aims to clearly qualify uncertainty.</li>
        </ul>

        <h2>3. Creative elements</h2>
        <p>To make history approachable, the assistant may paraphrase or adopt a conversational tone. It does not intentionally fabricate facts; creative language is used to enhance clarity and engagement, not to introduce falsehoods.</p>

        <h2>4. Known limitations</h2>
        <ul>
          <li>AI models can make mistakes or overstate confidence.</li>
          <li>Historical consensus can vary; dates, names, and interpretations may differ between sources.</li>
          <li>User prompts that ask for fiction may yield narrative content that should not be treated as fact.</li>
        </ul>

        <h2>5. Your role</h2>
        <ul>
          <li>Use critical thinking and consult cited sources where provided.</li>
          <li>Report inaccuracies to help us improve curation and prompts.</li>
        </ul>

        <h2>6. Safety and moderation</h2>
        <p>We apply filters to reduce harmful content and adhere to school-friendly guidelines. If you encounter inappropriate responses, please report them.</p>

        <h2>7. Updates</h2>
        <p>We iterate on prompts, sources, and safeguards. This policy will evolve as our tooling and content improve.</p>

        <div style={{marginTop:16}}>
          <Link className="btn" to="/register">Back to Register</Link>
          <Link className="btn" to="/dashboard" style={{marginLeft:8}}>Go to Dashboard</Link>
        </div>
      </div>
    </div>
  )
}
