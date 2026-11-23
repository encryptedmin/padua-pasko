/** Fetch JSON from the same-origin Django API with CSRF and a hard timeout. */
export class ApiError extends Error {
  constructor(code, message, status = 0, retryAfter = 0) {
    super(message || "Hindi maabot ang bunutan. Subukan ulit.");
    this.name = "ApiError";
    this.code = code || "request_failed";
    this.status = status;
    this.retryAfter = Number(retryAfter) || 0;
  }
}

function cookieValue(name) {
  const prefix = `${name}=`;
  const found = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith(prefix));
  return found ? decodeURIComponent(found.slice(prefix.length)) : "";
}

export async function apiRequest(path, { method = "GET", body, timeout = 10_000 } = {}) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeout);
  const headers = { Accept: "application/json" };
  const options = {
    method,
    credentials: "same-origin",
    cache: "no-store",
    referrerPolicy: "no-referrer",
    headers,
    signal: controller.signal,
  };

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    headers["X-CSRFToken"] = cookieValue("csrftoken");
    options.body = JSON.stringify(body);
  }

  try {
    const response = await fetch(path, options);
    const contentType = response.headers.get("content-type") || "";
    let data = null;
    if (contentType.includes("application/json")) {
      try { data = await response.json(); } catch { data = null; }
    }
    if (!response.ok || (data && !Array.isArray(data) && data.ok === false)) {
      const retryAfter = response.headers.get("Retry-After") || data?.retry_after || data?.seconds || 0;
      throw new ApiError(data?.error, data?.message, response.status, retryAfter);
    }
    return data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error?.name === "AbortError") throw new ApiError("timeout", "Medyo mabagal ang connection. Subukan ulit.", 0);
    throw new ApiError("network_error", "Walang connection sa bunutan. Pakisuri ang Wi-Fi at subukan ulit.", 0);
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export const apiGet = (path, timeout) => apiRequest(path, { method: "GET", timeout });
export const apiPost = (path, body, timeout) => apiRequest(path, { method: "POST", body, timeout });
