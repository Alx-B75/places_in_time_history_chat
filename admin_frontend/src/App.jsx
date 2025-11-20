import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import GuestChat from "./routes/GuestChat.jsx";
import Dashboard from './pages/Dashboard.jsx'
import UserLogin from './pages/UserLogin.jsx'
import UserRegister from './pages/UserRegister.jsx'
import GdprPolicy from './pages/GdprPolicy.jsx'
import AIPolicy from './pages/AIPolicy.jsx'
import RequireAuth from './components/RequireAuth.jsx'
import Home from './pages/Home.jsx'
import Threads from './pages/Threads.jsx'
import ThreadView from './pages/ThreadView.jsx'
import FigureSelect from './pages/FigureSelect.jsx'
import Layout from './components/Layout.jsx'
import AdminLLM from './pages/AdminLLM.jsx'
import FiguresPage from './pages/FiguresPage.jsx'
import RAGPage from './pages/RAGPage.jsx'
import ABPage from './pages/ABPage.jsx'

function NotFound() {
  return <div style={{textAlign:'center',marginTop:'4em',fontSize:'1.5em'}}>404 – Page Not Found</div>;
}

export default function App() {
  return (
    <Routes>
      {/* Default entry: auth gateway (Home handles redirect vs register view) */}
      <Route path="/" element={<Home />} />
      <Route path="/guest/:slug" element={<GuestChat />} />
  <Route path="/login" element={<UserLogin />} />
      <Route path="/register" element={<UserRegister />} />
  <Route path="/policy/gdpr" element={<GdprPolicy />} />
  <Route path="/policy/ai" element={<AIPolicy />} />
      <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
      <Route path="/threads" element={<RequireAuth><Threads /></RequireAuth>} />
      <Route path="/thread/:id" element={<RequireAuth><ThreadView /></RequireAuth>} />
  <Route path="/figures" element={<RequireAuth><FigureSelect /></RequireAuth>} />

      {/* Admin section */}
      <Route path="/admin" element={<Layout />}>
        <Route index element={<Navigate to="llm" replace />} />
        <Route path="llm" element={<AdminLLM />} />
        <Route path="figures" element={<FiguresPage />} />
        <Route path="rag" element={<RAGPage />} />
        <Route path="ab" element={<ABPage />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
