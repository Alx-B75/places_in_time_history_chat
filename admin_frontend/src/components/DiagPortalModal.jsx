import { createPortal } from "react";

export default function DiagPortalModal({ open = false, onClose, children }) {
  if (!open) return null;

  const backdrop = {
    position: "fixed",
    inset: 0,
    background: "rgba(0,0,0,0.65)",
    zIndex: 2147483647,        // above everything
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    pointerEvents: "auto",
  };

  const panel = {
    background: "#0b1220",
    border: "2px solid #22d3ee",
    color: "#eaf6f4",
    width: "min(92vw, 560px)",
    borderRadius: "14px",
    padding: "20px",
    boxShadow: "0 20px 60px rgba(0,0,0,.6)",
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial",
  };

  const btnRow = {
    display: "flex",
    gap: "12px",
    marginTop: "18px",
    justifyContent: "flex-end",
  };

  const btn = {
    padding: "10px 14px",
    borderRadius: "10px",
    border: "1px solid #22d3ee",
    background: "transparent",
    color: "#eaf6f4",
    cursor: "pointer",
  };

  return createPortal(
    <div style={backdrop} role="dialog" aria-modal="true">
      <div style={panel}>
        <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>
          Guest limit reached
        </div>
        <div style={{ opacity: 0.9 }}>
          You’ve reached the free guest limit. Please register or log in to continue.
        </div>
        <div style={btnRow}>
          <a href="/register" style={btn}>Register</a>
          <a href="/login" style={btn}>Log in</a>
          <button onClick={onClose} style={{ ...btn, borderColor: "#999" }}>Maybe later</button>
        </div>
      </div>
    </div>,
    document.body
  );
}
