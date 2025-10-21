import React, { useState, useEffect } from 'react'
import { patchLLMConfig, apiFetch } from '../lib/api'

const fields = [
  {name:'provider', label:'Provider', type:'text'},
  {name:'model', label:'Model', type:'text'},
  {name:'temperature', label:'Temperature', type:'number', step:0.1},
  {name:'max_tokens', label:'Max Tokens', type:'number'},
  {name:'api_base', label:'API Base', type:'text'},
  {name:'api_key', label:'API Key', type:'password'},
]



export default function AdminLLM(){
  const [form, setForm] = useState({})
  const [loaded, setLoaded] = useState({})
  const [msg, setMsg] = useState('')
  const [health, setHealth] = useState('')

  function handleChange(e){
    const {name, value} = e.target
    setForm(f => ({...f, [name]: value}))
  }

  async function loadCurrent(){
    setMsg('')
    try{
      const res = await apiFetch('/admin/llm/health').then(r=>r.json())
      setForm({
        provider: res.provider || '',
        model: res.model || '',
        temperature: res.temperature || '',
        max_tokens: res.max_tokens || '',
        api_base: res.api_base || '',
        api_key: res.api_key || ''
      })
      setLoaded({
        provider: res.provider || '',
        model: res.model || '',
        temperature: res.temperature || '',
        max_tokens: res.max_tokens || '',
        api_base: res.api_base || '',
        api_key: res.api_key || ''
      })
      setMsg('Loaded current config.')
    }catch(e){ setMsg('Failed to load config.') }
  }

  async function save(){
    setMsg('')
    const payload = {}
    for(const f of fields){
      if(form[f.name]!==undefined && form[f.name]!==loaded[f.name]){
        payload[f.name]=form[f.name]
      }
    }
    try{
      await patchLLMConfig(payload)
      setMsg('Saved!')
      setLoaded({...loaded, ...payload})
    }catch(e){ setMsg('Error: '+e.message) }
  }

  async function testHealth(){
    setHealth('...')
    try{
      const res = await apiFetch('/admin/llm/health').then(r=>r.json())
      setHealth(JSON.stringify(res))
    }catch(e){ setHealth('error') }
  }

  useEffect(() => { loadCurrent(); }, []);

  return (
    <div className="llm-admin-form">
      <h2>LLM Runtime Config</h2>
      <button onClick={loadCurrent}>Load Current</button>
      <form onSubmit={e=>{e.preventDefault();save()}}>
        {fields.map(f=>
          <div key={f.name} className="form-row">
            <label>{f.label}</label>
            <input name={f.name} type={f.type} step={f.step} value={form[f.name]||''} onChange={handleChange} />
          </div>
        )}
        <button type="submit">Save</button>
      </form>
      <div className="msg">{msg}</div>
      <hr/>
      <h3>Test Health</h3>
      <button onClick={testHealth}>Test Health</button>
      <pre>{health}</pre>
    </div>
  )
}
