
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import "./styles.css";
import { InteractionProvider } from './contexts/InteractionContext'

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <InteractionProvider>
        <App />
      </InteractionProvider>
    </BrowserRouter>
  </React.StrictMode>
);
