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
const endpointList = document.querySelector("#endpoint-list");
const apiExplorerMessage = document.querySelector("#api-explorer-message");

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

function resolveSchema(schema, specification) {
  if (schema?.$ref) {
    const path = schema.$ref.replace(/^#\//, "").split("/");
    return path.reduce((value, key) => value?.[key], specification) || {};
  }
  return schema || {};
}

function schemaExample(schema, specification) {
  const resolved = resolveSchema(schema, specification);
  if (resolved.example !== undefined) return resolved.example;
  if (resolved.default !== undefined) return resolved.default;
  if (resolved.enum?.length) return resolved.enum[0];
  if (resolved.type === "object" || resolved.properties) {
    return Object.fromEntries(
      Object.entries(resolved.properties || {}).map(([key, value]) => [
        key,
        schemaExample(value, specification),
      ]),
    );
  }
  if (resolved.type === "array") return [];
  if (resolved.type === "integer" || resolved.type === "number") return 0;
  if (resolved.type === "boolean") return false;
  return "";
}

function addEndpointField(container, label, name, value, fieldType = "text") {
  const wrapper = document.createElement("label");
  wrapper.className = "endpoint-field";
  wrapper.textContent = label;
  const input = document.createElement("input");
  input.type = fieldType;
  input.dataset.parameter = name;
  input.value = value ?? "";
  wrapper.append(input);
  container.append(wrapper);
}

function renderEndpoint(path, method, operation, specification) {
  const card = document.createElement("article");
  card.className = "endpoint-card";

  const heading = document.createElement("div");
  heading.className = "endpoint-title";
  const methodBadge = document.createElement("span");
  methodBadge.className = `method-badge method-${method}`;
  methodBadge.textContent = method.toUpperCase();
  const route = document.createElement("code");
  route.textContent = path;
  heading.append(methodBadge, route);
  card.append(heading);

  if (operation.summary || operation.description) {
    const description = document.createElement("p");
    description.className = "endpoint-description";
    description.textContent = operation.summary || operation.description;
    card.append(description);
  }

  const inputs = document.createElement("div");
  inputs.className = "endpoint-inputs";
  for (const parameter of operation.parameters || []) {
    addEndpointField(
      inputs,
      `${parameter.name}${parameter.required ? " (required)" : ""}`,
      `${parameter.in}:${parameter.name}`,
      parameter.example ?? parameter.schema?.default ?? "",
    );
  }

  const requestBody = operation.requestBody;
  const jsonBody = requestBody?.content?.["application/json"]?.schema;
  let bodyInput;
  if (jsonBody) {
    const bodyLabel = document.createElement("label");
    bodyLabel.className = "endpoint-body";
    bodyLabel.textContent = "Request body (JSON)";
    bodyInput = document.createElement("textarea");
    bodyInput.spellcheck = false;
    bodyInput.value = JSON.stringify(schemaExample(jsonBody, specification), null, 2);
    bodyLabel.append(bodyInput);
    inputs.append(bodyLabel);
  }
  if (inputs.childElementCount) card.append(inputs);

  const actions = document.createElement("div");
  actions.className = "endpoint-actions";
  const callButton = document.createElement("button");
  callButton.className = "button secondary";
  callButton.type = "button";
  callButton.textContent = "Call endpoint";
  const result = document.createElement("pre");
  result.className = "endpoint-result";
  result.hidden = true;
  result.setAttribute("aria-live", "polite");
  actions.append(callButton);
  card.append(actions, result);

  callButton.addEventListener("click", async () => {
    callButton.disabled = true;
    result.hidden = false;
    result.textContent = "Calling endpoint…";
    try {
      let requestPath = path;
      const query = new URLSearchParams();
      for (const input of inputs.querySelectorAll("[data-parameter]")) {
        const [location, name] = input.dataset.parameter.split(":");
        if (location === "path") {
          requestPath = requestPath.replace(`{${name}}`, encodeURIComponent(input.value.trim()));
        } else if (input.value !== "") {
          query.set(name, input.value);
        }
      }
      const queryString = query.toString();
      const headers = {};
      if (idToken) headers.Authorization = `Bearer ${idToken}`;
      const requestOptions = { method: method.toUpperCase(), headers };
      if (bodyInput) {
        requestOptions.headers["Content-Type"] = "application/json";
        requestOptions.body = JSON.stringify(JSON.parse(bodyInput.value));
      }
      const response = await fetch(
        `${apiBaseUrl}${requestPath}${queryString ? `?${queryString}` : ""}`,
        requestOptions,
      );
      const text = await response.text();
      let responseBody;
      try {
        responseBody = text ? JSON.parse(text) : null;
      } catch {
        responseBody = text;
      }
      result.textContent = `HTTP ${response.status} ${response.statusText}\n\n${
        typeof responseBody === "string" ? responseBody : JSON.stringify(responseBody, null, 2)
      }`;
    } catch (error) {
      result.textContent = `Request error: ${error.message}`;
    } finally {
      callButton.disabled = false;
    }
  });
  return card;
}

async function loadApiExplorer() {
  const reloadButton = document.querySelector("#reload-endpoints");
  reloadButton.disabled = true;
  endpointList.replaceChildren();
  apiExplorerMessage.textContent = "Loading API endpoints…";
  try {
    const specification = await responseJson(await fetch(`${apiBaseUrl}/openapi.json`));
    let count = 0;
    for (const [path, pathItem] of Object.entries(specification.paths || {})) {
      if (path === "/") continue;
      for (const method of ["get", "post", "put", "patch", "delete"]) {
        const operation = pathItem[method];
        if (!operation) continue;
        endpointList.append(renderEndpoint(path, method, operation, specification));
        count += 1;
      }
    }
    apiExplorerMessage.textContent = count
      ? `${count} endpoints loaded from the API specification.`
      : "The API specification contains no callable endpoints.";
  } catch (error) {
    apiExplorerMessage.textContent = `Could not load endpoints: ${error.message}`;
  } finally {
    reloadButton.disabled = false;
  }
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
    await loadApiExplorer();
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
document.querySelector("#reload-endpoints").addEventListener("click", loadApiExplorer);
for (const button of checkButtons) {
  button.addEventListener("click", () => testService(button.dataset.test));
}
})();
