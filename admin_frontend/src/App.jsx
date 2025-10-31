import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import GuestChat from "./routes/GuestChat.jsx";
import Dashboard from './pages/Dashboard.jsx'
import RequireAuth from './components/RequireAuth.jsx'

function NotFound() {
  return <div style={{textAlign:'center',marginTop:'4em',fontSize:'1.5em'}}>404 – Page Not Found</div>;
}

export default function App() {
  return (
    <Routes>
      {/* Safe default: point "/" to a public/guest page */}
      <Route path="/" element={<Navigate to="/guest/guy-fawkes" replace />} />
      <Route path="/guest/:slug" element={<GuestChat />} />
      <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
