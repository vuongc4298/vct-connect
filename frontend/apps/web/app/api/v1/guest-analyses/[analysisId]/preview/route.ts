import { NextRequest } from "next/server";
import { GUEST_COOKIE } from "../../_cookie";
import { proxyBackend } from "../../../../_backend";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ analysisId: string }> },
): Promise<Response> {
  const key = request.cookies.get(GUEST_COOKIE)?.value;
  if (!key || !/^[0-9a-f]{64}$/.test(key)) {
    return Response.json({ detail: "Preview not found" }, {
      status: 404,
      headers: { "Cache-Control": "private, no-store" },
    });
  }
  const { analysisId } = await context.params;
  const upstream = await proxyBackend(
    request,
    `/api/v1/guest-analyses/${encodeURIComponent(analysisId)}/preview`,
    key,
  );
  const headers = new Headers(upstream.headers);
  headers.set("Cache-Control", "private, no-store");
  return new Response(upstream.body, { status: upstream.status, headers });
}
