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
const statusMessage = document.querySelector("#status-message");

let idToken = "";
const checkButtons = [...document.querySelectorAll("[data-test]")];

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

async function testService(service) {
  const button = document.querySelector(`[data-test="${service}"]`);
  button.disabled = true;
  setStatus(service, "pending", "Checking…");
  statusMessage.textContent = "";

  const path = {
    api: "/health",
    database: "/ready",
    auth: "/v1/me",
  }[service];
  try {
    const options = service === "auth"
      ? { headers: { Authorization: `Bearer ${idToken}` } }
      : {};
    const result = await responseJson(await fetch(`${apiBaseUrl}${path}`, options));
    const state = service === "api" ? "Online" : service === "database" ? "Connected" : "Signed in";
    setStatus(service, "ok", state);
    if (service === "auth" && result.username) {
      userName.textContent = result.username.split("@")[0] || "there";
    }
    statusMessage.textContent = `${serviceLabel(service)} check passed at ${new Date().toLocaleTimeString()}.`;
  } catch (error) {
    setStatus(service, "error", service === "auth" ? "Check failed" : "Unavailable");
    if (service === "auth" && error.message === "A valid access token is required.") {
      signOut();
      signinMessage.textContent = "Your sign-in has expired. Please sign in again.";
    } else if (service === "database" && error.message.includes("Failed to fetch")) {
      statusMessage.textContent = "Database check failed. Verify the API CORS setting and service availability.";
    } else {
      statusMessage.textContent = `${serviceLabel(service)} check failed. Verify the service configuration and try again.`;
    }
  } finally {
    button.disabled = false;
  }
}

function serviceLabel(service) {
  return service === "api" ? "API" : service === "database" ? "Database" : "Authentication";
}

function signOut() {
  idToken = "";
  signinView.hidden = false;
  welcomeView.hidden = true;
  passwordInput.value = "";
}

if (isConfigured()) {
  signinButton.disabled = false;
} else {
  signinMessage.textContent = "The site configuration is unavailable. Ask the repository administrator to configure the Pages deployment secrets.";
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
    for (const service of ["api", "database", "auth"]) {
      setStatus(service, "pending", "Not tested");
    }
    statusMessage.textContent = "Test each service using its own button.";
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

document.querySelector("#signout-button").addEventListener("click", signOut);
for (const button of checkButtons) {
  button.addEventListener("click", () => testService(button.dataset.test));
}
})();
