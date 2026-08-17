import { NextResponse } from 'next/server';
import {
  AGENT_URL,
  ID_TOKEN_COOKIE,
  PROFILE_COOKIE,
  getProfile,
} from '@/lib/agent';

export async function GET() {
  return NextResponse.json({ profile: await getProfile() });
}

/** Sign in. The ID token goes into an HttpOnly cookie; only the profile is readable. */
export async function POST(request: Request) {
  const { email } = await request.json();

  const upstream = await fetch(`${AGENT_URL}/auth/demo-signin`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ email }),
    cache: 'no-store',
  });

  if (!upstream.ok) {
    return NextResponse.json(
      { error: 'sign-in failed', detail: await upstream.text() },
      { status: upstream.status },
    );
  }

  const { id_token, profile } = await upstream.json();
  const response = NextResponse.json({ profile });

  response.cookies.set(ID_TOKEN_COOKIE, id_token, {
    httpOnly: true,
    sameSite: 'lax',
    path: '/',
    maxAge: 3600,
    // Localhost is http in development; a deployment sets NODE_ENV=production.
    secure: process.env.NODE_ENV === 'production',
  });
  response.cookies.set(PROFILE_COOKIE, encodeURIComponent(JSON.stringify(profile)), {
    httpOnly: false,
    sameSite: 'lax',
    path: '/',
    maxAge: 3600,
  });

  return response;
}

export async function DELETE() {
  const response = NextResponse.json({ ok: true });
  response.cookies.delete(ID_TOKEN_COOKIE);
  response.cookies.delete(PROFILE_COOKIE);
  return response;
}
