"use strict";
const form = document.querySelector("#login-form");
const password = document.querySelector("#password");
const toggle = document.querySelector("#toggle-password");
const message = document.querySelector("#login-message");
toggle.addEventListener("click", () => {
  const showing = password.type === "password";
  password.type = showing ? "text" : "password";
  toggle.textContent = showing ? "Ocultar" : "Mostrar";
  toggle.setAttribute("aria-pressed", String(showing));
  toggle.setAttribute("aria-label", showing ? "Ocultar senha" : "Mostrar senha");
});
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = form.querySelector('[type="submit"]');
  submit.disabled = true;
  form.setAttribute("aria-busy", "true");
  message.dataset.state = "pending";
  message.textContent = "Verificando acesso…";
  try {
    const response = await fetch("/demo/login", {
      method: "POST", signal: AbortSignal.timeout(10000), credentials: "same-origin", redirect: "error",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({username: form.username.value.trim(), password: password.value})
    });
    if (response.ok) { password.value = ""; location.replace("/"); return; }
    message.dataset.state = "error";
    message.textContent = response.status === 429
      ? "Muitas tentativas. Aguarde alguns segundos e tente novamente."
      : response.status === 401 ? "Usuário ou senha incorretos. Confira e tente novamente."
      : "Não foi possível entrar. Tente novamente.";
  } catch (_) {
    message.dataset.state = "error";
    message.textContent = "Não foi possível conectar. Confira sua conexão e tente novamente.";
  } finally { submit.disabled = false; form.setAttribute("aria-busy", "false"); }
});
