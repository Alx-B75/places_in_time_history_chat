import React, { useState } from 'react'

function api(path, opts){
  const token = sessionStorage.getItem('adminToken')
  return apiFetch(path, opts).then(r=>r.json())
}

export default function LLMPage(){
  const [status, setStatus] = useState(null)
  async function check(){
    setStatus('loading')
    try{
      const res = await api('/admin/llm/health')
      setStatus(JSON.stringify(res))
    }catch(e){
      setStatus('error')
    }
  }
  return (
    <div>
      <h2>LLM Runtime</h2>
      <button onClick={check}>Run Health Check</button>
      <pre>{status}</pre>
      <h3>Edit runtime config</h3>
      <p>Coming soon — will call PATCH /admin/llm</p>
    </div>
  )
}
