import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import ReactDOM from "react-dom";

const MAX_QUESTIONS = 3;

function portalTarget() {
  if (typeof document === "undefined") return null;
  return document.getElementById("portal-root") || document.body;
}

function QuotaModal({ open, onRegister, onLater, figureName }) {
  if (!open) return null;
  const node = portalTarget();
  if (!node) return null;

  return ReactDOM.createPortal(
    <div className="pit-modal-overlay" role="dialog" aria-modal="true" data-test="quota-modal">
      <div className="pit-modal-card">
        <h3 style={{ marginTop: 0 }}>You’ve hit the 3-question limit</h3>
        <p>
          That was your last free question. If you register, you can continue this conversation with <strong>{figureName || 'this figure'}</strong> and keep exploring more.
        </p>
        <div className="pit-modal-actions">
          <button className="pit-btn" onClick={onLater}>Back to Places in Time</button>
          <button className="pit-btn primary" onClick={onRegister}>Register to continue</button>
        </div>
      </div>
    </div>,
    node
  );
}

export default function GuestChat() {
  const { slug } = useParams();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [qaCount, setQaCount] = useState(0);
  const [boot, setBoot] = useState("booting"); // booting | ready | error
  const [status, setStatus] = useState("");
  const [disabled, setDisabled] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [figure, setFigure] = useState(null);
  const siteRoot = (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'))
    ? 'http://127.0.0.1:8000'
    : 'https://www.places-in-time.com';

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`/guest/start/${encodeURIComponent(slug)}`, {
          method: "POST",
          credentials: "include",
        });
        if (!r.ok) {
          setBoot("error");
          return;
        }
        const startData = await r.json().catch(() => null);
        setBoot("ready");
        // Mark presence of guest session for later upgrade attempt post-registration
        try { sessionStorage.setItem('hasGuestSession', '1') } catch(_){ }
        // Fetch figure details for UI (image, name, short summary)
        const figureSlug = startData?.figure_slug || slug;
        try {
          const fRes = await fetch(`/figures/${encodeURIComponent(figureSlug)}`);
          if (fRes.ok) {
            const fJson = await fRes.json();
            setFigure(fJson);
          }
        } catch (err) {
          // ignore; figure remains null
          console.warn("Failed to load figure details", err);
        }
      } catch (e) {
        console.error("guest start failed", e);
        setBoot("error");
      }
    })();
  }, [slug]);

  async function handleSend() {
    if (!input.trim() || boot !== "ready" || disabled) return;

    if (qaCount >= MAX_QUESTIONS) {
      setShowModal(true);
      return;
    }

    setMessages((m) => [...m, { role: "user", text: input }]);
  setStatus(`${figure?.name || "Guide"} is thinking…`);
    setDisabled(true);

    try {
      const res = await fetch("/guest/ask", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: input }),
      });

      if (!res.ok) {
        if (res.status === 403 || res.status === 429) {
          setShowModal(true);
          setDisabled(false);
          return;
        }
        setStatus(`Error ${res.status}: Unable to get an answer.`);
        setDisabled(false);
        return;
      }

      const data = await res.json();
  setMessages((m) => [...m, { role: "assistant", text: data.answer || "(no answer)" }]);
      setQaCount((c) => c + 1);
      // If quota exhausted on this question, flag upgrade hint
      try {
        const remaining = (Math.max(0, (3 - (qaCount + 1)))).toString()
        sessionStorage.setItem('guestRemaining', remaining)
      }catch(_){ }
      setStatus("");
      setDisabled(false);
      setInput("");
    } catch (e) {
      console.error("ask failed", e);
      setStatus("Network error. Please try again.");
      setDisabled(false);
    }
  }

  if (boot === "error") return <div style={{padding:24, textAlign:'center'}}>Failed to start guest session.</div>;

  return (
    <div className="wrap" style={{ maxWidth: 860 }}>
      {/* Shared banner with logo for branding consistency */}
      {/* Logo integrated into a framed card to match page components */}
      <div
        className="card panel logo-card"
        style={{
          margin:'16px 0',
          display:'flex',
          justifyContent:'center',
          alignItems:'center',
          padding:'18px',
          background:'#0f172a',
          border:'1px solid rgba(255,255,255,.06)',
          borderRadius:14,
          boxShadow:'0 12px 24px rgba(0,0,0,.35)'
        }}
      >
        <div className="brand-mark" aria-hidden style={{width:140, height:140, borderRadius:24, overflow:'hidden'}}>
          <img src="/static/logo.png" alt="Places in Time" style={{width:'100%', height:'100%', objectFit:'cover', borderRadius:'inherit'}}/>
        </div>
      </div>

      {/* Centered figure hero */}
      <div className="figure-hero card" style={{marginBottom:18, display:'flex', flexDirection:'column', alignItems:'center', textAlign:'center', gap:16}}>
        {figure?.image_url ? (
          <img src={figure.image_url} alt={figure.name} className="avatar-lg" style={{width:140,height:140,boxShadow:'0 4px 16px rgba(0,0,0,.4)',border:'1px solid rgba(255,255,255,.18)', borderRadius:24, objectFit:'cover'}} />
        ) : (
          <div className="avatar-lg" style={{width:140,height:140,background:'#0a1228',border:'1px solid rgba(255,255,255,.18)', borderRadius:24}} />
        )}
        <div className="figure-hero-text" style={{maxWidth:720}}>
          <div className="figure-name-serif" style={{fontSize:'clamp(26px,3.5vw,38px)', fontWeight:600, textAlign:'center'}}>{figure?.name || 'Guide'}</div>
          <div className="figure-desc-serif" style={{fontSize:'clamp(17px,2.2vw,22px)', lineHeight:1.6, textAlign:'left'}}>{figure?.short_summary || 'Ask a question to learn more.'}</div>
        </div>
        <div className="status" style={{textAlign:'center', minHeight:'1.2em'}}>{status}</div>
      </div>

      <div className="card chat-card" style={{marginBottom:24, overflow:'hidden'}}>
        <div className="messages" style={{maxHeight:360}}>
          {messages.length === 0 ? (
            <div className="muted">No messages yet. Ask your first question.</div>
          ) : (
            messages.map((m,i) => (
              <div key={i} className={m.role === 'user' ? 'msg-user' : 'msg-assistant'}>{m.text}</div>
            ))
          )}
        </div>
        <form onSubmit={(e)=>{e.preventDefault(); handleSend();}} className="compose" style={{flexDirection:'column',alignItems:'stretch', width:'100%', boxSizing:'border-box'}}>
          <textarea
            value={input}
            onChange={(e)=>setInput(e.target.value)}
            onKeyDown={(e)=>{ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); handleSend(); } }}
            placeholder={`Ask ${figure?.name || 'the guide'} a question… (Enter to send)`}
            disabled={disabled}
            style={{width:'100%',fontSize:'1rem',padding:'12px 14px',borderRadius:'var(--radius-md)',border:'1px solid var(--border)',background:'#0a1820',color:'var(--text)', boxSizing:'border-box'}}
            rows={4}
          />
          <div style={{display:'flex',justifyContent:'flex-end',width:'100%'}}>
            <button type="submit" className="send-btn" disabled={disabled}>{disabled ? 'Thinking…' : 'Send'}</button>
          </div>
        </form>
      </div>

      <QuotaModal
        open={showModal || window._forceGuestModal === true}
        figureName={figure?.name}
        onRegister={() => { window.location.href = `${siteRoot}/register`; }}
        onLater={() => { window.location.href = `${siteRoot}/`; }}
      />
    </div>
  );
}
