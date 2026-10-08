import { proxyBackend } from "../../../../../../_backend";

export const dynamic = "force-dynamic";

export async function POST(request: Request, context: { params: Promise<{ runId: string; ordinal: string }> }): Promise<Response> {
  const { runId, ordinal } = await context.params;
  if (!/^[0-9a-f-]{36}$/i.test(runId) || !/^\d+$/.test(ordinal)) {
    return Response.json({ detail: "Invalid review case" }, { status: 422 });
  }
  return proxyBackend(request, `/api/v1/internal/review-cases/${encodeURIComponent(runId)}/${encodeURIComponent(ordinal)}/label`);
}
