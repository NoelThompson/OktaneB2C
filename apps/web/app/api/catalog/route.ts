import { NextResponse } from 'next/server';
import { getCatalog } from '@/lib/catalog';

/** Re-read stock levels so the tiles update after a restock without a reload. */
export async function GET() {
  return NextResponse.json({ products: await getCatalog() });
}
