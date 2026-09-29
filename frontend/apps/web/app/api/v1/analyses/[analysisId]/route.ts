import { proxyBackend } from "../../../_backend";

export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  context: { params: Promise<{ analysisId: string }> },
): Promise<Response> {
  const { analysisId } = await context.params;
  return proxyBackend(request, `/api/v1/analyses/${encodeURIComponent(analysisId)}`);
}
