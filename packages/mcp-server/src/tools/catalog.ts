import { getDb } from '../db.ts';

export interface VariantRow {
  sku: string;
  size: string;
  label: string;
  price_cents: number;
  stock: number;
}

export interface ProductRow {
  sku: string;
  name: string;
  category: string;
  icon: string;
  price_cents: number;
  blurb: string;
  sizing_guide: string | null;
  variants: VariantRow[];
}

function variantsFor(productSku: string): VariantRow[] {
  return getDb()
    .prepare(
      `SELECT sku, size, label, price_cents, stock
         FROM variants WHERE product_sku = ? ORDER BY price_cents DESC`,
    )
    .all(productSku) as unknown as VariantRow[];
}

/**
 * Free-text product search. `query` matches name, category, or blurb so the
 * agent can find "basketball" without knowing our SKU scheme.
 */
export function search(args: { query?: string; category?: string; limit?: number }): {
  products: ProductRow[];
} {
  const limit = Math.min(Math.max(args.limit ?? 10, 1), 50);
  const like = `%${(args.query ?? '').toLowerCase()}%`;

  const rows = getDb()
    .prepare(
      `SELECT sku, name, category, icon, price_cents, blurb, sizing_guide
         FROM products
        WHERE (?1 = '%%' OR lower(name) LIKE ?1
                          OR lower(category) LIKE ?1
                          OR lower(blurb) LIKE ?1)
          AND (?2 IS NULL OR category = ?2)
        ORDER BY name
        LIMIT ?3`,
    )
    .all(like, args.category ?? null, limit) as unknown as Omit<ProductRow, 'variants'>[];

  return {
    products: rows.map((r) => ({ ...r, variants: variantsFor(r.sku) })),
  };
}

export interface SizingRuleRow {
  size: string;
  circumference: string;
  label: string;
  min_age: number;
  max_age: number;
  notes: string;
}

/**
 * The sizing table for a guide, optionally narrowed to the rule matching an
 * age. This is what keeps the size-7 recommendation grounded in catalog data
 * instead of leaving it to the model to recall.
 */
export function sizingGuide(args: { guide: string; age?: number }): {
  guide: string;
  rules: SizingRuleRow[];
  recommended?: SizingRuleRow;
} {
  const rules = getDb()
    .prepare(
      `SELECT size, circumference, label, min_age, max_age, notes
         FROM sizing_rules WHERE guide = ? ORDER BY min_age DESC`,
    )
    .all(args.guide) as unknown as SizingRuleRow[];

  const recommended =
    typeof args.age === 'number'
      ? rules.find((r) => args.age! >= r.min_age && args.age! <= r.max_age)
      : undefined;

  return { guide: args.guide, rules, recommended };
}
