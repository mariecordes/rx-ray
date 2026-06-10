import { NextResponse } from "next/server";

export async function proxyJsonResponse(response: Response) {
  const text = await response.text();
  const payload = parseJsonOrFallback(text, response);

  return NextResponse.json(payload, { status: response.status });
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
