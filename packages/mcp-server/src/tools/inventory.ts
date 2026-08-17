import { getDb } from '../db.ts';

export interface StockRow {
  sku: string;
  product_sku: string;
  product_name: string;
  size: string;
  label: string;
  price_cents: number;
  stock: number;
  in_stock: boolean;
}

const SELECT = `
  SELECT v.sku, v.product_sku, p.name AS product_name,
         v.size, v.label, v.price_cents, v.stock
    FROM variants v JOIN products p ON p.sku = v.product_sku`;

function decorate(rows: Omit<StockRow, 'in_stock'>[]): StockRow[] {
  return rows.map((r) => ({ ...r, in_stock: r.stock > 0 }));
}

/**
 * Stock for a specific variant SKU, or for every variant of a product, or for
 * one size of a product. The agent reaches this with an `inventory:read`
 * token — a catalog-audience token cannot get here.
 */
export function check(args: {
  sku?: string;
  product_sku?: string;
  size?: string;
}): { variants: StockRow[] } {
  const d = getDb();

  if (args.sku) {
    return {
      variants: decorate(
        d.prepare(`${SELECT} WHERE v.sku = ?`).all(args.sku) as unknown as Omit<
          StockRow,
          'in_stock'
        >[],
      ),
    };
  }

  if (args.product_sku && args.size) {
    return {
      variants: decorate(
        d
          .prepare(`${SELECT} WHERE v.product_sku = ? AND v.size = ?`)
          .all(args.product_sku, args.size) as unknown as Omit<StockRow, 'in_stock'>[],
      ),
    };
  }

  if (args.product_sku) {
    return {
      variants: decorate(
        d
          .prepare(`${SELECT} WHERE v.product_sku = ? ORDER BY v.price_cents DESC`)
          .all(args.product_sku) as unknown as Omit<StockRow, 'in_stock'>[],
      ),
    };
  }

  throw new Error('inventory.check requires sku or product_sku');
}

/**
 * Demo-only restock. Sets absolute stock for a variant and returns the before
 * and after so the telemetry drawer can show the transition that wakes the
 * standing intent.
 */
export function restock(args: { sku: string; stock: number }): {
  sku: string;
  before: number;
  after: number;
} {
  const d = getDb();
  const row = d.prepare('SELECT stock FROM variants WHERE sku = ?').get(args.sku) as
    | { stock: number }
    | undefined;
  if (!row) throw new Error(`unknown variant ${args.sku}`);

  d.prepare('UPDATE variants SET stock = ? WHERE sku = ?').run(args.stock, args.sku);
  return { sku: args.sku, before: row.stock, after: args.stock };
}
