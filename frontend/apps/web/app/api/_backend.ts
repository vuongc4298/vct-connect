const API_ORIGIN = process.env.API_INTERNAL_ORIGIN ?? "http://127.0.0.1:8000";
const MAX_HTML_BYTES = 2_000_000;

async function boundedUpload(request: Request): Promise<Uint8Array<ArrayBuffer> | null> {
  const reader = request.body?.getReader();
  if (!reader) return new Uint8Array();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > MAX_HTML_BYTES) {
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
    if (upload && Number(request.headers.get("content-length")) > MAX_HTML_BYTES) {
      return Response.json({ detail: "HTML page exceeds 2 MB" }, { status: 413 });
    }
    const uploadBody = upload ? await boundedUpload(request) : undefined;
    if (upload && uploadBody === null) {
      return Response.json({ detail: "HTML page exceeds 2 MB" }, { status: 413 });
    }
    const upstream = await fetch(`${API_ORIGIN}${path}`, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined
        : upload ? new Blob([uploadBody!]) : await request.text(),
      cache: "no-store",
    });
    const responseHeaders = new Headers();
    const upstreamContentType = upstream.headers.get("content-type");
    if (upstreamContentType) responseHeaders.set("content-type", upstreamContentType);
    return new Response(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch (cause) {
    return Response.json(
      {
        detail: "Backend unavailable. Check the FastAPI process and API_INTERNAL_ORIGIN.",
      },
      { status: 503 },
    );
  }
}
