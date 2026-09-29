import { randomBytes } from "node:crypto";
import { NextRequest } from "next/server";
import { proxyBackend } from "../../_backend";
import { GUEST_COOKIE } from "./_cookie";

export const dynamic = "force-dynamic";

function validKey(value: string | undefined): value is string {
  return !!value && /^[0-9a-f]{64}$/.test(value);
}

export async function POST(request: NextRequest): Promise<Response> {
  const existing = request.cookies.get(GUEST_COOKIE)?.value;
  const key = validKey(existing) ? existing : randomBytes(32).toString("hex");
  const upstream = await proxyBackend(request, "/api/v1/guest-analyses", key);
  if (validKey(existing)) return upstream;
  const headers = new Headers(upstream.headers);
  const secure = new URL(request.url).protocol === "https:" ? "; Secure" : "";
  headers.append(
    "Set-Cookie",
    `${GUEST_COOKIE}=${key}; Path=/api/v1/guest-analyses; Max-Age=2592000; HttpOnly; SameSite=Lax${secure}`,
  );
  return new Response(upstream.body, { status: upstream.status, headers });
}
