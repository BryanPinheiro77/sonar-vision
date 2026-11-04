"use strict";
const logoutButton = document.querySelector("#logout");
logoutButton?.addEventListener("click", async () => {
  logoutButton.disabled = true;
  try {
    const response = await fetch("/demo/logout", {method: "POST", credentials: "same-origin"});
    if (!response.ok) throw new Error("logout");
    location.replace("/");
  } catch (_) { logoutButton.textContent = "Tentar sair novamente"; logoutButton.disabled = false; }
});
