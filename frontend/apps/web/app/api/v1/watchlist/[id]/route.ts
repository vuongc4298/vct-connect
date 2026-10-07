import { proxyBackend } from "../../../_backend";

export const dynamic = "force-dynamic";

async function forward(
  request: Request,
  context: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await context.params;
  const upstream = await proxyBackend(request, `/api/v1/watchlist/${encodeURIComponent(id)}`);
  const headers = new Headers(upstream.headers);
  headers.set("Cache-Control", "private, no-store");
  return new Response(upstream.body, { status: upstream.status, headers });
}

export const POST = forward;
export const DELETE = forward;
