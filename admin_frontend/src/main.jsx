
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import "./styles.css";
import { InteractionProvider } from './contexts/InteractionContext'
import { AuthProvider } from './contexts/AuthContext.jsx'

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <InteractionProvider>
          <App />
        </InteractionProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
