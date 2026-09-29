import { proxyBackend } from "../../_backend";

export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<Response> {
  return proxyBackend(request, "/api/v1/analyses");
}
