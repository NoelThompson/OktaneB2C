import { NextResponse } from 'next/server';
import {
  ID_TOKEN_COOKIE,
  PROFILE_COOKIE,
  agentFetch,
  getIdToken,
} from '@/lib/agent';

export async function POST(request: Request) {
  const idToken = await getIdToken();
  if (!idToken) {
    return NextResponse.json({ error: 'sign in to use the assistant' }, { status: 401 });
  }

  const { message } = await request.json();
  if (typeof message !== 'string' || !message.trim()) {
    return NextResponse.json({ error: 'message required' }, { status: 400 });
  }

  const upstream = await agentFetch('/agent/chat', {
    method: 'POST',
    body: JSON.stringify({ message, id_token: idToken }),
  });

  if (upstream.status === 401) {
    // The agent rejected the token, so the cookie is worthless. Drop it rather
    // than leaving the header showing a signed-in shopper who cannot chat.
    const expired = NextResponse.json(
      { error: 'your session expired — sign in again' },
      { status: 401 },
    );
    expired.cookies.delete(ID_TOKEN_COOKIE);
    expired.cookies.delete(PROFILE_COOKIE);
    return expired;
  }

  return NextResponse.json(await upstream.json(), { status: upstream.status });
}
