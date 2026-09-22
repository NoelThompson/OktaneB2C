import { NextResponse } from 'next/server';
import { agentFetch, getIdToken, ID_TOKEN_COOKIE, PROFILE_COOKIE } from '@/lib/agent';

/**
 * Full sign-out: drop this app's cookie, reset the demo SKU to out-of-stock,
 * and hand back Okta's own logout URL so the browser can clear that session
 * too. All three happen server-side before the client redirects, so a
 * refresh mid-flow can't leave the storefront half-signed-out.
 */
export async function POST() {
  const idToken = await getIdToken();

  let logoutUrl: string | null = null;
  try {
    const upstream = await agentFetch(
      `/auth/logout-url${idToken ? `?id_token=${encodeURIComponent(idToken)}` : ''}`,
    );
    if (upstream.ok) {
      logoutUrl = (await upstream.json()).logout_url ?? null;
    }
  } catch {
    // Best-effort — a shopper should still be able to sign out locally even
    // if the agent is unreachable.
  }

  try {
    await agentFetch('/demo/restock', {
      method: 'POST',
      body: JSON.stringify({ stock: 0 }),
    });
  } catch {
    // Same trade-off: a failed reset should not block sign-out.
  }

  const response = NextResponse.json({ logout_url: logoutUrl });
  response.cookies.delete(ID_TOKEN_COOKIE);
  response.cookies.delete(PROFILE_COOKIE);
  return response;
}
