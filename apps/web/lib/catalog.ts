import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { agentJson } from './agent';
import type { Product } from './types';

/**
 * Public catalog for the storefront.
 *
 * Deliberately unauthenticated: a real storefront's product listing is public.
 * The AI agent takes a different path — it calls the MCP server with a scoped
 * access token, because it acts on a shopper's behalf.
 *
 * Read live so a restock is visible on the tiles. The seed file is a fallback
 * for when the backend is not running, so the page still renders.
 */
export async function getCatalog(): Promise<Product[]> {
  try {
    const live = await agentJson<{ products: Product[] }>('/demo/catalog');
    if (live.products?.length) return live.products;
  } catch {
    // fall through to the seed file
  }
  return seedCatalog();
}

async function seedCatalog(): Promise<Product[]> {
  const file = path.join(process.cwd(), '..', '..', 'data', 'catalog.json');
  const parsed = JSON.parse(await readFile(file, 'utf8')) as { products: Product[] };
  return parsed.products;
}
