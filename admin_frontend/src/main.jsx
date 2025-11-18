import "./lib/fetchBase.js";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import "./styles.css";
import { InteractionProvider } from './contexts/InteractionContext'
import { AuthProvider } from './contexts/AuthContext.jsx'

const Wrapper = import.meta.env.PROD ? React.StrictMode : React.Fragment;

ReactDOM.createRoot(document.getElementById("root")).render(
  <Wrapper>
    <BrowserRouter>
      <AuthProvider>
        <InteractionProvider>
          <App />
        </InteractionProvider>
      </AuthProvider>
    </BrowserRouter>
  </Wrapper>
);
