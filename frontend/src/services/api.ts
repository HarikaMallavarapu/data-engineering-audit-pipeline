export class ApiClientError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

export interface ApiPage<T> {
  items: T[];
  total: number;
  page?: number;
  page_size?: number;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE.replace(/\/$/, "")}${path}`, init);
  } catch {
    throw new ApiClientError("DataTrace could not reach the API. Check that the backend is running.", 0, "network_error");
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = (body as { error?: { code?: string; message?: string } } | null)?.error;
    throw new ApiClientError(
      error?.message || `Request failed with status ${response.status}.`,
      response.status,
      error?.code || "request_failed",
    );
  }
  if (body === null) {
    throw new ApiClientError("The API returned an unreadable response.", response.status, "invalid_response");
  }
  return body as T;
}

export async function apiDownload(path: string): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE.replace(/\/$/, "")}${path}`);
  } catch {
    throw new ApiClientError("DataTrace could not reach the API. Check that the backend is running.", 0, "network_error");
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const error = (body as { error?: { code?: string; message?: string } } | null)?.error;
    throw new ApiClientError(error?.message || `Request failed with status ${response.status}.`, response.status, error?.code || "request_failed");
  }
  return response.blob();
}

export async function checkHealth(): Promise<{ status: string }> {
  let response: Response;
  try {
    response = await fetch("/health");
  } catch {
    throw new ApiClientError("DataTrace could not reach the API. Check that the backend is running.", 0, "network_error");
  }
  if (!response.ok) throw new ApiClientError("Backend health check failed.", response.status, "health_check_failed");
  return (await response.json()) as { status: string };
}
