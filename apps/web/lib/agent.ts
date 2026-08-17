/**
 * Server-side client for the agent service.
 *
 * The shopper's ID token lives in an HttpOnly cookie and is read only here, in
 * route handlers. The browser never sees a token, so nothing in the client
 * bundle can leak or replay one.
 */

import { cookies } from 'next/headers';

export const AGENT_URL = process.env.AGENT_URL ?? 'http://localhost:8788';
export const ID_TOKEN_COOKIE = 'oktane_idt';
export const PROFILE_COOKIE = 'oktane_profile';

export async function getIdToken(): Promise<string | null> {
  const store = await cookies();
  return store.get(ID_TOKEN_COOKIE)?.value ?? null;
}

export async function getProfile(): Promise<{
  sub: string;
  name: string;
  email: string;
} | null> {
  const store = await cookies();
  const raw = store.get(PROFILE_COOKIE)?.value;
  if (!raw) return null;
  try {
    return JSON.parse(decodeURIComponent(raw));
  } catch {
    return null;
  }
}

export async function agentFetch(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  return fetch(`${AGENT_URL}${path}`, {
    ...init,
    headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) },
    cache: 'no-store',
  });
}

export async function agentJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await agentFetch(path, init);
  if (!response.ok) {
    throw new Error(`agent ${path} -> ${response.status} ${await response.text()}`);
  }
  return (await response.json()) as T;
}
