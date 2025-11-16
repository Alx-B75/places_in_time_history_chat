(function () {
  // Support both login and register pages. The login page uses id="login-form",
  // while the register page uses id="register-form" and may use 'username' input.
  const form = document.getElementById("login-form") || document.getElementById("register-form");
  if (!form) return;

  const emailEl = document.getElementById("email") || document.getElementById("username");
  const passwordEl = document.getElementById("password");
  const loginBtn = document.getElementById("login-btn");
  // If register button is not explicitly present, fall back to the form's submit button
  const registerBtn = document.getElementById("register-btn") || form.querySelector('button[type="submit"]');
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
      // help the SPA discover tokens consistently during dev
      sessionStorage.setItem("userToken", data.access_token);
      // debug log to ensure we reached the client-side store flow
      // eslint-disable-next-line no-console
      console.debug('[static_frontend] storeAuth setting token for user_id=', data.user_id);
      // Development helper: also set a host-scoped cookie so dev frontends
      // running on different ports (Vite on :5173) can read the token.
      // This is non-httpOnly and intended for local dev only.
      document.cookie = `pit_access_token=${data.access_token}; path=/`;
      // Try to set common local host variants to improve visibility across
      // 'localhost' and '127.0.0.1' dev hosts. These may silently fail in some
      // browsers but are harmless attempts for convenience.
      try{ document.cookie = `pit_access_token=${data.access_token}; path=/; domain=localhost`; }catch(_){}
      try{ document.cookie = `pit_access_token=${data.access_token}; path=/; domain=127.0.0.1`; }catch(_){}
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
      const dev = (location.hostname === '127.0.0.1' || location.hostname === 'localhost') && location.port === '8000'
      if (dev) {
        // send to Vite SPA dashboard in dev
        window.location.href = `http://127.0.0.1:5173/dashboard`;
      } else {
        // Take user directly to their threads console
        const uid = data?.user_id || localStorage.getItem('user_id');
        if (uid) window.location.href = `/user/${uid}/threads`;
        else window.location.href = `/threads`;
      }
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
    // Only enforce GDPR / AI acknowledgement if the checkboxes exist on the page.
    if ((gdprEl && !gdprConsent) || (aiAckEl && !aiAck)) {
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
      const dev = (location.hostname === '127.0.0.1' || location.hostname === 'localhost') && location.port === '8000'
      if (dev) {
        window.location.href = `http://127.0.0.1:5173/dashboard`;
      } else {
        const uid = data?.user_id || localStorage.getItem('user_id');
        if (uid) window.location.href = `/user/${uid}/threads`;
        else window.location.href = `/threads`;
      }
    } catch {
      showError("Network error during registration.");
    }
  }

  if (loginBtn) loginBtn.addEventListener("click", (e) => { e.preventDefault(); login(); });
  if (registerBtn) registerBtn.addEventListener("click", (e) => { e.preventDefault(); register(); });

  // Also handle direct form submit (covers register pages where the button has no id)
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    if (form.id === 'register-form') return register();
    return login();
  });
})();

