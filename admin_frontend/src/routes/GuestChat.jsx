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
      setStatus("");
      setDisabled(false);
      setInput("");
    } catch (e) {
      console.error("ask failed", e);
      setStatus("Network error. Please try again.");
      setDisabled(false);
    }
  }

  if (boot === "error") return <div>Failed to start guest session.</div>;

  return (
    <div style={{ maxWidth: 720, margin: "24px auto" }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 12 }}>
        {figure?.image_url ? (
          <img src={figure.image_url} alt={figure.name} style={{ width: 64, height: 64, borderRadius: 8, objectFit: "cover" }} />
        ) : (
          <div style={{ width: 64, height: 64, borderRadius: 8, background: "#e2e8f0" }} />
        )}
        <div>
          <div style={{ fontWeight: 600 }}>{figure?.name || "Guide"}</div>
          <div style={{ color: "#64748b", fontSize: 13 }}>{figure?.short_summary || "Ask a question to learn more."}</div>
        </div>
        <div style={{ marginLeft: "auto", color: "#94a3b8" }}>{status}</div>
      </div>

      <div style={{ border: "1px solid #334155", borderRadius: 10, padding: 12, minHeight: 200 }}>
        {messages.map((m, i) => (
          <div key={i} style={{ margin: "6px 0" }}>
            <strong>{m.role === "user" ? "You" : (figure?.name || "Guide")}:</strong> {m.text}
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
          rows={3}
          style={{ flex: 1 }}
          placeholder={`Ask ${figure?.name || 'the guide'} a question…`}
        />
        <button disabled={disabled} onClick={handleSend}>Send</button>
      </div>

      <QuotaModal
        open={showModal || window._forceGuestModal === true}
        figureName={figure?.name}
        onRegister={() => { window.location.href = `${siteRoot}/register`; }}
        onLater={() => { window.location.href = `${siteRoot}/`; }}
      >
        {/* children not used but kept for extensibility */}
      </QuotaModal>
    </div>
  );
}
