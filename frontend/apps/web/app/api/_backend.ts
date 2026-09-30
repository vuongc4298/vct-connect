const API_ORIGIN = process.env.API_INTERNAL_ORIGIN ?? "http://127.0.0.1:8000";
const MAX_HTML_BYTES = 2_000_000;
const MAX_CAPTURE_BYTES = 16_384;
const EXTENSION_ORIGIN = "chrome-extension://klggcepemjjbphjclpiabgpfgdbgiljj";

function withExtensionCors(request: Request, response: Response): Response {
  if (request.headers.get("origin") !== EXTENSION_ORIGIN) return response;
  const headers = new Headers(response.headers);
  headers.set("access-control-allow-origin", EXTENSION_ORIGIN);
  headers.set("access-control-allow-methods", "GET, POST, OPTIONS");
  headers.set("access-control-allow-headers", "authorization, content-type");
  headers.set("vary", "Origin");
  return new Response(response.body, { status: response.status, headers });
}

async function boundedUpload(request: Request, maximum = MAX_HTML_BYTES): Promise<Uint8Array<ArrayBuffer> | null> {
  const reader = request.body?.getReader();
  if (!reader) return new Uint8Array();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > maximum) {
        await reader.cancel();
        return null;
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const body = new Uint8Array(new ArrayBuffer(total));
  let offset = 0;
  for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength; }
  return body;
}

export async function proxyBackend(
  request: Request, path: string, guestKey?: string,
): Promise<Response> {
  const headers = new Headers();
  const authorization = request.headers.get("authorization");
  const contentType = request.headers.get("content-type");
  if (authorization && !guestKey) headers.set("authorization", authorization);
  if (contentType) headers.set("content-type", contentType);
  if (guestKey) headers.set("x-vct-guest-key", guestKey);

  try {
    const upload = path === "/api/v1/analyses/import" || path.startsWith("/api/v1/analyses/import?");
    const capture = path === "/api/v1/analyses/capture";
    const maximum = capture ? MAX_CAPTURE_BYTES : MAX_HTML_BYTES;
    if ((upload || capture) && Number(request.headers.get("content-length")) > maximum) {
      return withExtensionCors(request, Response.json({ detail: capture ? "Capture exceeds 16 KB" : "HTML page exceeds 2 MB" }, { status: 413 }));
    }
    const uploadBody = upload || capture ? await boundedUpload(request, maximum) : undefined;
    if ((upload || capture) && uploadBody === null) {
      return withExtensionCors(request, Response.json({ detail: capture ? "Capture exceeds 16 KB" : "HTML page exceeds 2 MB" }, { status: 413 }));
    }
    const upstream = await fetch(`${API_ORIGIN}${path}`, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined
        : upload || capture ? new Blob([uploadBody!]) : await request.text(),
      cache: "no-store",
    });
    const responseHeaders = new Headers();
    const upstreamContentType = upstream.headers.get("content-type");
    if (upstreamContentType) responseHeaders.set("content-type", upstreamContentType);
    return withExtensionCors(request, new Response(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: responseHeaders,
    }));
  } catch (cause) {
    return withExtensionCors(request, Response.json(
      {
        detail: "Backend unavailable. Check the FastAPI process and API_INTERNAL_ORIGIN.",
      },
      { status: 503 },
    ));
  }
}
