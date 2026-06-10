const DEFAULT_RETRY_ATTEMPTS = 5;
const DEFAULT_RETRY_DELAY_MS = 350;

type RequestJsonOptions = {
  attempts?: number;
  retryDelayMs?: number;
  userMessage?: string;
};

export class ApiClientError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
  }
}

export async function requestJsonWithRetry<T>(
  url: string,
  init: RequestInit,
  options: RequestJsonOptions = {}
): Promise<T> {
  const attempts = options.attempts ?? DEFAULT_RETRY_ATTEMPTS;
  const retryDelayMs = options.retryDelayMs ?? DEFAULT_RETRY_DELAY_MS;
  const userMessage =
    options.userMessage ??
    "The app server had trouble returning API data. Please try again.";
  let lastError: unknown = null;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await requestJson<T>(url, init);
    } catch (error) {
      lastError = error;
      console.warn(
        `API request failed, attempt ${attempt}/${attempts}: ${url}`,
        error
      );
      if (attempt < attempts) {
        await wait(retryDelayMs * attempt);
      }
    }
  }

  throw new ApiClientError(
    `${userMessage} If this keeps happening, restart the frontend dev server.`,
    lastError instanceof ApiClientError ? lastError.status : undefined
  );
}

async function requestJson<T>(url: string, init: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const text = await response.text();
  const payload = parseJsonPayload(text, url);

  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? String(payload.detail)
        : `Request failed with status ${response.status}`;
    throw new ApiClientError(detail, response.status);
  }

  return payload as T;
}

function parseJsonPayload(text: string, url: string): unknown {
  if (!text.trim()) {
    return {};
  }
  try {
    return JSON.parse(text);
  } catch (error) {
    const preview = text.replace(/\s+/g, " ").slice(0, 120);
    throw new ApiClientError(
      `Expected JSON from ${url}, but received: ${preview}`,
      error instanceof ApiClientError ? error.status : undefined
    );
  }
}

function wait(milliseconds: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}
