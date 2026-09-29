import type {
  Analysis, SubmitAnalysisRequest, SubmitAnalysisResponse,
  SubmitGuestAnalysisRequest, SubmitGuestAnalysisResponse,
} from "@vct/contracts";

export type RequestAuth = {
  getToken: () => Promise<string | null>;
};

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

export const REQUEST_TIMEOUT_MS = 10_000;

function abortable<T>(operation: Promise<T>, signal: AbortSignal): Promise<T> {
  if (signal.aborted) return Promise.reject(signal.reason);
  return new Promise((resolve, reject) => {
    const aborted = () => reject(signal.reason);
    signal.addEventListener("abort", aborted, { once: true });
    operation.then(
      value => { signal.removeEventListener("abort", aborted); resolve(value); },
      error => { signal.removeEventListener("abort", aborted); reject(error); },
    );
  });
}

async function request<T>(
  input: string,
  createInit: () => Promise<RequestInit>,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const init = await abortable(createInit(), controller.signal);
    const response = await abortable(
      fetch(input, { ...init, signal: controller.signal }),
      controller.signal,
    );
    return await abortable(read<T>(response), controller.signal);
  } catch (cause) {
    if (controller.signal.aborted) {
      throw new ApiError("Request timed out", 408);
    }
    throw cause;
  } finally {
    clearTimeout(timer);
  }
}

async function read<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (Array.isArray(body.detail)) {
        message = body.detail.map((entry: { msg?: string }) => entry.msg).filter(Boolean).join("; ") || message;
      } else if (typeof body.detail === "string") {
        message = body.detail;
      }
    } catch { /* The status remains useful when the server sends no JSON. */ }
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as T;
}

async function authorizationHeaders(auth?: RequestAuth): Promise<Record<string, string>> {
  const token = await auth?.getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function submitAnalysis(
  body: SubmitAnalysisRequest,
  auth?: RequestAuth,
): Promise<SubmitAnalysisResponse> {
  return request<SubmitAnalysisResponse>("/api/v1/analyses", async () => ({
    method: "POST",
    headers: { "Content-Type": "application/json", ...await authorizationHeaders(auth) },
    body: JSON.stringify(body),
  }));
}

export async function getAnalysis(id: string, auth?: RequestAuth): Promise<Analysis> {
  return request<Analysis>(`/api/v1/analyses/${encodeURIComponent(id)}`, async () => ({
    cache: "no-store",
    headers: await authorizationHeaders(auth),
  }));
}

export async function submitGuestAnalysis(
  body: SubmitGuestAnalysisRequest,
): Promise<SubmitGuestAnalysisResponse> {
  return request<SubmitGuestAnalysisResponse>("/api/v1/guest-analyses", async () => ({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: "same-origin",
  }));
}

export async function getGuestAnalysis(id: string): Promise<Analysis> {
  return request<Analysis>(`/api/v1/guest-analyses/${encodeURIComponent(id)}`, async () => ({
    cache: "no-store",
    credentials: "same-origin",
  }));
}
