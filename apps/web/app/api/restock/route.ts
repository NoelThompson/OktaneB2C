import { NextResponse } from 'next/server';
import { agentFetch } from '@/lib/agent';

/**
 * Beat 6: the only scripted event in the demo. Everything downstream of it —
 * matching standing intents, raising an approval, notifying the shopper — runs
 * the same code a real system would.
 */
export async function POST(request: Request) {
  const { sku, stock } = await request.json();

  const upstream = await agentFetch('/demo/restock', {
    method: 'POST',
    body: JSON.stringify({ sku, stock }),
  });

  return NextResponse.json(await upstream.json(), { status: upstream.status });
}
