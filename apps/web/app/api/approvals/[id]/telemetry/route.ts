import { NextResponse } from 'next/server';
import { agentFetch } from '@/lib/agent';

/**
 * Trace for events raised outside a chat turn — the restock, the step-up, and
 * the orders:write exchange that releases the order. Without this the drawer
 * would stop just before the climax.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const upstream = await agentFetch(`/telemetry/${encodeURIComponent(id)}`);
  return NextResponse.json(await upstream.json(), { status: upstream.status });
}
