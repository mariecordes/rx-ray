import { NextRequest, NextResponse } from "next/server";

const LOCAL_BACKEND_URL = "http://localhost:8000";

type BackendUrlResult =
  | { ok: true; value: string }
  | { ok: false; message: string };

export async function proxyBackendPost(request: NextRequest, path: string) {
  const backendUrl = resolveBackendUrl();
  if (!backendUrl.ok) {
    return NextResponse.json({ detail: backendUrl.message }, { status: 500 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { detail: "Request body must be valid JSON." },
      { status: 400 }
    );
  }

  const target = `${backendUrl.value}${path}`;
  try {
    const response = await fetch(target, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      cache: "no-store",
    });

    return proxyJsonResponse(response);
  } catch (error) {
    return NextResponse.json(
      {
        detail:
          "Backend request failed before a response was received. Check BACKEND_URL and backend availability.",
        target,
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 502 }
    );
  }
}

export async function proxyJsonResponse(response: Response) {
  const text = await response.text();
  const payload = parseJsonOrFallback(text, response);

  return NextResponse.json(payload, { status: response.status });
}

function resolveBackendUrl(): BackendUrlResult {
  const configured = process.env.BACKEND_URL?.trim();
  if (configured) {
    return { ok: true, value: stripTrailingSlashes(configured) };
  }

  if (isProductionRuntime()) {
    return {
      ok: false,
      message:
        "Backend unavailable: BACKEND_URL is not configured for this deployment.",
    };
  }

  return { ok: true, value: LOCAL_BACKEND_URL };
}

function stripTrailingSlashes(value: string) {
  return value.replace(/\/+$/, "");
}

function isProductionRuntime() {
  return process.env.VERCEL === "1" || process.env.NODE_ENV === "production";
}

function parseJsonOrFallback(text: string, response: Response) {
  if (!text.trim()) {
    return response.ok
      ? {}
      : { detail: `Backend request failed with status ${response.status}` };
  }
  try {
    return JSON.parse(text);
  } catch {
    return {
      detail:
        "Backend returned a non-JSON response. This can happen during a dev-server restart or transient backend error.",
      status: response.status,
      preview: text.replace(/\s+/g, " ").slice(0, 240),
    };
  }
}
