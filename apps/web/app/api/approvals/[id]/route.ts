import { NextResponse } from 'next/server';
import { agentFetch } from '@/lib/agent';

/** The CIBA-shaped poll the chat panel uses while it waits for the shopper. */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const upstream = await agentFetch(`/approvals/${encodeURIComponent(id)}`);
  return NextResponse.json(await upstream.json(), { status: upstream.status });
}
