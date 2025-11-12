import React from 'react'
import { Link } from 'react-router-dom'
import LogoCard from '../components/LogoCard.jsx'

export default function GdprPolicy(){
  return (
    <div className="wrap" style={{maxWidth:860}}>
      <LogoCard wide to="/dashboard" />
      <div className="banner" style={{margin:'8px 0', justifyContent:'space-between'}}>
        <div className="brand-title">
          <h1 style={{margin:0}}>Privacy Policy (GDPR)</h1>
          <div className="muted">How we collect, use, and protect your data</div>
        </div>
        <div className="banner-actions">
          <Link className="btn" to="/register">Back to Register</Link>
        </div>
      </div>
      <div className="card panel" style={{padding:22}}>
        <h2>1. Who we are</h2>
        <p>Places in Time is an educational application that enables users to explore historical topics and figures using a conversational interface. This policy describes how we process personal data in compliance with the EU General Data Protection Regulation (GDPR) and applicable UK data protection law.</p>

        <h2>2. What data we collect</h2>
        <ul>
          <li>Account data: email address and hashed password.</li>
          <li>Usage data: conversation threads and messages you submit; favorites you mark; timestamps and basic technical logs.</li>
          <li>Cookies/tokens: session tokens for authentication and security.</li>
        </ul>

        <h2>3. Why we process your data (lawful bases)</h2>
        <ul>
          <li>Contract: to create your account and deliver the service (store threads, let you resume conversations).</li>
          <li>Consent: to save optional preferences like favorites and to email you if you opt in.</li>
          <li>Legitimate interests: to protect the service (debugging, security logs, abuse prevention).</li>
        </ul>

        <h2>4. How we use your data</h2>
        <ul>
          <li>Operate the app, authenticate you, store and display your threads.</li>
          <li>Improve the experience (e.g., performance, relevance of results) using aggregated, anonymised metrics.</li>
          <li>Protect the service, investigate abuse or security incidents.</li>
        </ul>

        <h2>5. Data sharing</h2>
        <p>We do not sell your personal data. We may share limited data with infrastructure providers strictly as needed to run the service (hosting, storage, vector database, model providers). Where model providers are used to generate responses, prompts and relevant context may be processed by those providers to fulfil your request.</p>

        <h2>6. International transfers</h2>
        <p>Our infrastructure or model providers may process data in other jurisdictions with appropriate safeguards (such as Standard Contractual Clauses). We aim to minimise personal data in prompts and use pseudonymisation where possible.</p>

        <h2>7. Retention</h2>
        <p>Account data is retained while your account is active. You may delete threads individually or request account deletion, which removes associated personal data unless retention is required for legal or security reasons.</p>

        <h2>8. Your rights</h2>
        <ul>
          <li>Access, rectification, deletion, and portability of your data.</li>
          <li>Restriction or objection to processing in certain circumstances.</li>
          <li>Withdraw consent at any time where processing is based on consent.</li>
        </ul>
        <p>Contact us via the support channel provided in the app to exercise your rights.</p>

        <h2>9. Security</h2>
        <p>We apply industry-standard safeguards such as encryption in transit, hashed passwords, and strict access controls. No system is perfect—please notify us immediately if you suspect unauthorised access to your account.</p>

        <h2>10. Children</h2>
        <p>The service is intended for educational use by a general audience. Where used by minors, a parent/guardian or school administrator should supervise usage and consent to processing as applicable.</p>

        <h2>11. Changes</h2>
        <p>We may update this policy as the service evolves. Material changes will be announced in the app with a clear effective date.</p>

        <div style={{marginTop:16}}>
          <Link className="btn" to="/register">Back to Register</Link>
          <Link className="btn" to="/dashboard" style={{marginLeft:8}}>Go to Dashboard</Link>
        </div>
      </div>
    </div>
  )
}
