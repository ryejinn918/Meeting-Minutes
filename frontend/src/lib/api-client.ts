import type { ApiErrorEnvelope } from "@/types/api";
import { supabase } from "@/lib/supabase";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/$/, "");

export class ApiClientError extends Error {
  constructor(public readonly status: number, public readonly payload: ApiErrorEnvelope) {
    super(payload.error.message);
  }
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  if (!apiBaseUrl) throw new Error("API 서버 주소가 설정되지 않았습니다.");
  if (!supabase) throw new Error("Supabase 환경변수가 설정되지 않았습니다.");
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session) throw new Error("로그인이 필요합니다.");
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${data.session.access_token}`,
      ...init?.headers,
    },
  });
  if (!response.ok) {
    let payload: ApiErrorEnvelope;
    try {
      payload = (await response.json()) as ApiErrorEnvelope;
    } catch {
      payload = { error: { code: "UNKNOWN_ERROR", message: "요청을 처리하지 못했습니다.", request_id: "unknown" } };
    }
    throw new ApiClientError(response.status, payload);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
