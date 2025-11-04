(function () {
  const form = document.getElementById("login-form");
  if (!form) return;

  const emailEl = document.getElementById("email");
  const passwordEl = document.getElementById("password");
  const loginBtn = document.getElementById("login-btn");
  const registerBtn = document.getElementById("register-btn");
  const msgEl = document.getElementById("message");
  const gdprEl = document.getElementById("gdpr-consent");
  const aiAckEl = document.getElementById("ai-ack");

  function showError(text) {
    msgEl.textContent = text || "Something went wrong.";
    msgEl.style.display = "block";
    msgEl.style.color = "#fecaca";
  }
  function showInfo(text) {
    msgEl.textContent = text || "";
    msgEl.style.display = text ? "block" : "none";
    msgEl.style.color = "#9cc3c8";
  }
  function clearMsg() {
    msgEl.textContent = "";
    msgEl.style.display = "none";
  }

  function storeAuth(data) {
    if (!data || !data.access_token) throw new Error("No token in response");
    localStorage.setItem("access_token", data.access_token);
    if (data.user_id != null) localStorage.setItem("user_id", String(data.user_id));
    if (data.username) localStorage.setItem("username", data.username);
    try{
      // Development helper: also set a host-scoped cookie so dev frontends
      // running on different ports (Vite on :5173) can read the token.
      // This is non-httpOnly and intended for local dev only.
      document.cookie = `pit_access_token=${data.access_token}; path=/`;
    }catch(e){ /* ignore when not in browser */ }
  }

  function validEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  }

  function strongEnough(pw) {
    if (typeof pw !== "string" || pw.length < 8) return false;
    const hasUpper = /[A-Z]/.test(pw);
    const hasLower = /[a-z]/.test(pw);
    const hasNum = /[0-9]/.test(pw);
    const hasSpecial = /[^A-Za-z0-9]/.test(pw);
    return hasUpper && hasLower && hasNum && hasSpecial;
  }

  async function login() {
    clearMsg();
    const email = (emailEl.value || "").trim();
    const password = passwordEl.value || "";
    if (!validEmail(email)) {
      showError("Enter a valid email address.");
      emailEl.focus();
      return;
    }
    if (!password) {
      showError("Password is required.");
      passwordEl.focus();
      return;
    }

    try {
      showInfo("Signing you in…");
      const res = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: email, password })
      });
      if (!res.ok) {
        const text = await res.text();
        showError(text || `Login failed (${res.status}).`);
        return;
      }
      const data = await res.json();
      storeAuth(data);
      const uid = data.user_id ?? localStorage.getItem("user_id");
      window.location.href = `/user/${uid}/threads`;
    } catch {
      showError("Network error during login.");
    }
  }

  async function register() {
    clearMsg();
    const email = (emailEl.value || "").trim();
    const password = passwordEl.value || "";
    const gdprConsent = !!gdprEl?.checked;
    const aiAck = !!aiAckEl?.checked;

    if (!validEmail(email)) {
      showError("Enter a valid email address to register.");
      emailEl.focus();
      return;
    }
    if (!strongEnough(password)) {
      showError("Password must include uppercase, lowercase, number, and special character.");
      passwordEl.focus();
      return;
    }
    if (!gdprConsent || !aiAck) {
      showError("Please accept the GDPR consent and AI disclosure to register.");
      return;
    }

    try {
      showInfo("Creating your account…");
      const res = await fetch("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: email,
          email,
          password,
          gdpr_consent: gdprConsent,
          ai_ack: aiAck
        })
      });
      if (!res.ok) {
        const text = await res.text();
        showError(text || `Registration failed (${res.status}).`);
        return;
      }
      const data = await res.json();
      storeAuth(data);
      const uid = data.user_id ?? localStorage.getItem("user_id");
      window.location.href = `/user/${uid}/threads`;
    } catch {
      showError("Network error during registration.");
    }
  }

  loginBtn.addEventListener("click", (e) => { e.preventDefault(); login(); });
  registerBtn.addEventListener("click", (e) => { e.preventDefault(); register(); });
})();
