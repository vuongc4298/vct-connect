import { proxyBackend } from "../../_backend";

export const dynamic = "force-dynamic";

export async function GET(request: Request): Promise<Response> {
  const upstream = await proxyBackend(request, "/api/v1/me");
  const headers = new Headers(upstream.headers);
  headers.set("Cache-Control", "private, no-store");
  return new Response(upstream.body, { status: upstream.status, headers });
}
