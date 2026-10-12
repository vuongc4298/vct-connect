import { proxyBackend } from "../../../../_backend";

export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  context: { params: Promise<{ analysisId: string }> },
): Promise<Response> {
  const { analysisId } = await context.params;
  return proxyBackend(
    request,
    `/api/v1/analyses/${encodeURIComponent(analysisId)}/report`,
  );
}

export async function OPTIONS(request: Request): Promise<Response> {
  if (request.headers.get("origin") !== "chrome-extension://klggcepemjjbphjclpiabgpfgdbgiljj") {
    return new Response(null, { status: 403 });
  }
  return new Response(null, { status: 204, headers: {
    "Access-Control-Allow-Origin": request.headers.get("origin")!,
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "authorization, content-type",
    "Vary": "Origin",
  } });
}
