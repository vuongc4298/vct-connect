const API_ORIGIN = process.env.API_INTERNAL_ORIGIN ?? "http://127.0.0.1:8000";

export async function proxyBackend(request: Request, path: string): Promise<Response> {
  const headers = new Headers();
  const authorization = request.headers.get("authorization");
  const contentType = request.headers.get("content-type");
  if (authorization) headers.set("authorization", authorization);
  if (contentType) headers.set("content-type", contentType);

  try {
    const upstream = await fetch(`${API_ORIGIN}${path}`, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.text(),
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
