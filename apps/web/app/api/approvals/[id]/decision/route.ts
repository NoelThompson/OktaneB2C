import { NextResponse } from 'next/server';
import { agentFetch } from '@/lib/agent';

/**
 * Release or refuse the purchase.
 *
 * POST only, and the one-time decision token issued by the step-up callback
 * travels in the body. A GET approve link would be prefetchable by a mail
 * scanner, which would let a link previewer buy a basketball.
 */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const { decision, decision_token } = await request.json();

  const upstream = await agentFetch(
    `/approvals/${encodeURIComponent(id)}/decision`,
    { method: 'POST', body: JSON.stringify({ decision, decision_token }) },
  );

  return NextResponse.json(await upstream.json(), { status: upstream.status });
}
