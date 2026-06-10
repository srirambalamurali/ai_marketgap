import { API_BASE } from "@/services/api";

export type AuthUser = {
  id: string;
  name: string;
  email: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: "bearer" | string;
  user: AuthUser;
};

const TOKEN_KEY = "mg_auth_token";
const COOKIE_NAME = "mg_auth_token";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 7;

function authHeaders(token?: string) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    try {
      const parsed = text ? JSON.parse(text) : null;
      throw new Error(parsed?.detail || parsed?.message || parsed?.error || text || `Request failed: ${res.status}`);
    } catch {
      throw new Error(text || `Request failed: ${res.status}`);
    }
  }
  return res.json() as Promise<T>;
}

export function getStoredToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function storeToken(token: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
  document.cookie = `${COOKIE_NAME}=${encodeURIComponent(token)}; path=/; max-age=${COOKIE_MAX_AGE}; samesite=lax`;
}

export function clearToken() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  document.cookie = `${COOKIE_NAME}=; path=/; max-age=0; samesite=lax`;
}

export async function register(payload: { name: string; email: string; password: string }) {
  const data = await request<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  storeToken(data.access_token);
  return data;
}

export async function login(payload: { email: string; password: string }) {
  const data = await request<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  storeToken(data.access_token);
  return data;
}

export async function getMe(token?: string | null) {
  const authToken = token ?? getStoredToken();
  if (!authToken) return null;
  const headers: Record<string, string> = {
    Authorization: `Bearer ${authToken}`,
  };
  return request<AuthUser>("/auth/me", {
    headers,
  });
}

export async function logout() {
  clearToken();
}
