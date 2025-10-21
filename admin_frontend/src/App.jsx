import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import AdminLLM from "./pages/AdminLLM.jsx";
import FiguresPage from "./pages/FiguresPage.jsx";
import RAGPage from "./pages/RAGPage.jsx";
import ABPage from "./pages/ABPage.jsx";

function RequireAuth({ children }) {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  if (!token) return <Navigate to="/admin/ui" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/admin/ui" replace />} />
      <Route path="/admin/ui" element={<LoginPage />} />
      <Route path="/admin" element={<RequireAuth><Layout /></RequireAuth>}>
        <Route path="llm" element={<AdminLLM />} />
        <Route path="figures" element={<FiguresPage />} />
        <Route path="rag" element={<RAGPage />} />
        <Route path="ab" element={<ABPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/admin/ui" replace />} />
    </Routes>
  );
}
