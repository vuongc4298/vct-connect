import { proxyBackend } from "../../../../_backend";

export const dynamic = "force-dynamic";

export async function POST(request: Request, context: { params: Promise<{ phase: string }> }): Promise<Response> {
  const { phase } = await context.params;
  if (!["begin", "finish"].includes(phase)) return Response.json({ detail: "Not found" }, { status: 404 });
  return proxyBackend(request, `/api/v1/analyses/collection/${phase}`);
}

export async function OPTIONS(request: Request): Promise<Response> {
  const origin = request.headers.get("origin");
  if (origin !== "chrome-extension://klggcepemjjbphjclpiabgpfgdbgiljj") return new Response(null, { status: 403 });
  return new Response(null, { status: 204, headers: {
    "Access-Control-Allow-Origin": origin, "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "authorization, content-type", "Vary": "Origin",
  } });
}
