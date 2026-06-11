import { NextRequest } from "next/server";
import { proxyJsonResponse } from "@/app/api/_proxy";

const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  const body = await request.json();
  const response = await fetch(`${backendUrl}/query-answer`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    cache: "no-store",
  });

  return proxyJsonResponse(response);
}
