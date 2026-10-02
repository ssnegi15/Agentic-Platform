"use strict";

(() => {
const config = window.AGENT_PLATFORM_CONFIG || {};
const apiBaseUrl = (config.apiBaseUrl || "").replace(/\/+$/, "");
const signinView = document.querySelector("#signin-view");
const welcomeView = document.querySelector("#welcome-view");
const signinForm = document.querySelector("#signin-form");
const signinButton = document.querySelector("#signin-button");
const signinMessage = document.querySelector("#signin-message");
const emailInput = document.querySelector("#email");
const passwordInput = document.querySelector("#password");
const userName = document.querySelector("#user-name");
const userEmail = document.querySelector("#user-email");
const refreshButton = document.querySelector("#refresh-status");

let idToken = "";

function isConfigured() {
  return apiBaseUrl.startsWith("https://")
    && !apiBaseUrl.includes("YOUR-RENDER-SERVICE")
    && Boolean(config.firebaseApiKey)
    && config.firebaseApiKey !== "YOUR-FIREBASE-WEB-API-KEY";
}

async function responseJson(response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body?.error?.message || body?.detail || `Request failed (${response.status}).`);
  }
  return body;
}

function setStatus(prefix, state, label) {
  document.querySelector(`#${prefix}-dot`).className = `status-indicator ${state}`;
  document.querySelector(`#${prefix}-status`).textContent = label;
}

async function refreshStatus() {
  refreshButton.disabled = true;
  setStatus("api", "pending", "Checking…");
  setStatus("database", "pending", "Checking…");
  setStatus("auth", "pending", "Checking…");

  const checks = await Promise.allSettled([
    fetch(`${apiBaseUrl}/health`).then(responseJson),
    fetch(`${apiBaseUrl}/ready`).then(responseJson),
    fetch(`${apiBaseUrl}/v1/me`, {
      headers: { Authorization: `Bearer ${idToken}` },
    }).then(responseJson),
  ]);

  const [api, database, auth] = checks;
  setStatus("api", api.status === "fulfilled" ? "ok" : "error",
    api.status === "fulfilled" ? "Online" : "Unavailable");
  setStatus("database", database.status === "fulfilled" ? "ok" : "error",
    database.status === "fulfilled" ? "Connected" : "Unavailable");
  setStatus("auth", auth.status === "fulfilled" ? "ok" : "error",
    auth.status === "fulfilled" ? "Signed in" : "Token check failed");

  if (auth.status === "fulfilled" && auth.value.username) {
    userName.textContent = auth.value.username.split("@")[0] || "there";
  } else if (
    auth.status === "rejected"
    && auth.reason.message === "A valid access token is required."
  ) {
    signOut();
    signinMessage.textContent = "Your sign-in has expired. Please sign in again.";
  }

  document.querySelector("#checked-at").textContent =
    `Last checked ${new Date().toLocaleTimeString()}`;
  refreshButton.disabled = false;
}

function signOut() {
  idToken = "";
  signinView.hidden = false;
  welcomeView.hidden = true;
  passwordInput.value = "";
}

if (isConfigured()) {
  signinButton.disabled = false;
  for (const id of ["api-docs", "dashboard-docs"]) {
    document.querySelector(`#${id}`).href = `${apiBaseUrl}/docs`;
  }
  document.querySelector("#health-link").href = `${apiBaseUrl}/health`;
} else {
  signinMessage.textContent = "Configure the API URL and Firebase web API key in docs/app-config.js, then publish the Pages site.";
}

signinForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  signinMessage.textContent = "";
  signinButton.disabled = true;

  try {
    const result = await responseJson(await fetch(
      `https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${encodeURIComponent(config.firebaseApiKey)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: emailInput.value.trim(),
          password: passwordInput.value,
          returnSecureToken: true,
        }),
      },
    ));
    idToken = result.idToken;
    const email = result.email || emailInput.value.trim();
    userEmail.textContent = email;
    userName.textContent = email.split("@")[0] || "there";
    passwordInput.value = "";
    signinView.hidden = true;
    welcomeView.hidden = false;
    await refreshStatus();
  } catch (error) {
    const errors = {
      INVALID_LOGIN_CREDENTIALS: "Email or password is incorrect.",
      EMAIL_NOT_FOUND: "Email or password is incorrect.",
      INVALID_PASSWORD: "Email or password is incorrect.",
      INVALID_EMAIL: "Enter a valid email address.",
      OPERATION_NOT_ALLOWED: "Enable Email/Password sign-in in Firebase Authentication.",
      TOO_MANY_ATTEMPTS_TRY_LATER: "Too many attempts. Wait a little and try again.",
    };
    signinMessage.textContent = errors[error.message]
      || "Sign-in failed. Check your Firebase account and configuration.";
  } finally {
    signinButton.disabled = !isConfigured();
  }
});

refreshButton.addEventListener("click", refreshStatus);
document.querySelector("#signout-button").addEventListener("click", signOut);
})();
