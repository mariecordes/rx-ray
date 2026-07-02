import { NextRequest } from "next/server";
import { proxyBackendPost } from "@/app/api/_proxy";

export async function POST(request: NextRequest) {
  return proxyBackendPost(request, "/query-understanding");
}
