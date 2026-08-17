import { DatabaseSync } from 'node:sqlite';
import { readFileSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, '..', '..', '..');

export const DB_PATH =
  process.env.OKTANE_DB_PATH ?? path.join(repoRoot, 'data', 'oktane.db');
export const CATALOG_PATH = path.join(repoRoot, 'data', 'catalog.json');

let db: DatabaseSync | null = null;

export function getDb(): DatabaseSync {
  if (db) return db;
  mkdirSync(path.dirname(DB_PATH), { recursive: true });
  db = new DatabaseSync(DB_PATH);
  db.exec('PRAGMA journal_mode = WAL');
  db.exec('PRAGMA foreign_keys = ON');
  migrate(db);
  return db;
}

function migrate(d: DatabaseSync): void {
  d.exec(`
    CREATE TABLE IF NOT EXISTS products (
      sku          TEXT PRIMARY KEY,
      name         TEXT NOT NULL,
      category     TEXT NOT NULL,
      icon         TEXT NOT NULL,
      price_cents  INTEGER NOT NULL,
      blurb        TEXT NOT NULL,
      sizing_guide TEXT
    );

    CREATE TABLE IF NOT EXISTS variants (
      sku          TEXT PRIMARY KEY,
      product_sku  TEXT NOT NULL REFERENCES products(sku),
      size         TEXT NOT NULL,
      label        TEXT NOT NULL,
      price_cents  INTEGER NOT NULL,
      stock        INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS sizing_rules (
      guide         TEXT NOT NULL,
      size          TEXT NOT NULL,
      circumference TEXT NOT NULL,
      label         TEXT NOT NULL,
      min_age       INTEGER NOT NULL,
      max_age       INTEGER NOT NULL,
      notes         TEXT NOT NULL,
      PRIMARY KEY (guide, size)
    );

    CREATE TABLE IF NOT EXISTS orders (
      order_id        TEXT PRIMARY KEY,
      subject         TEXT NOT NULL,
      variant_sku     TEXT NOT NULL REFERENCES variants(sku),
      qty             INTEGER NOT NULL,
      unit_cents      INTEGER NOT NULL,
      total_cents     INTEGER NOT NULL,
      placed_by_agent TEXT,
      approval_id     TEXT,
      idempotency_key TEXT UNIQUE,
      created_at      TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_variants_product ON variants(product_sku);
    CREATE INDEX IF NOT EXISTS idx_orders_subject ON orders(subject);
  `);
}

/** Load catalog.json into the DB. Destructive for catalog tables; orders survive. */
export function seed(): { products: number; variants: number; rules: number } {
  const d = getDb();
  const raw = JSON.parse(readFileSync(CATALOG_PATH, 'utf8'));

  d.exec('DELETE FROM sizing_rules');

  // Upsert rather than delete: placed orders hold a foreign key onto variants.
  const insProduct = d.prepare(
    `INSERT INTO products (sku, name, category, icon, price_cents, blurb, sizing_guide)
     VALUES (?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(sku) DO UPDATE SET
       name = excluded.name, category = excluded.category, icon = excluded.icon,
       price_cents = excluded.price_cents, blurb = excluded.blurb,
       sizing_guide = excluded.sizing_guide`,
  );
  const insVariant = d.prepare(
    `INSERT INTO variants (sku, product_sku, size, label, price_cents, stock)
     VALUES (?, ?, ?, ?, ?, ?)
     ON CONFLICT(sku) DO UPDATE SET
       product_sku = excluded.product_sku, size = excluded.size,
       label = excluded.label, price_cents = excluded.price_cents,
       stock = excluded.stock`,
  );
  const insRule = d.prepare(
    `INSERT INTO sizing_rules (guide, size, circumference, label, min_age, max_age, notes)
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
  );

  let variants = 0;
  for (const p of raw.products) {
    insProduct.run(
      p.sku,
      p.name,
      p.category,
      p.icon,
      p.price_cents,
      p.blurb,
      p.sizing_guide ?? null,
    );
    for (const v of p.variants) {
      insVariant.run(v.sku, p.sku, v.size, v.label, v.price_cents, v.stock);
      variants += 1;
    }
  }

  let rules = 0;
  for (const [guide, def] of Object.entries<any>(raw.sizing_guides)) {
    for (const r of def.rules) {
      insRule.run(
        guide,
        r.size,
        r.circumference,
        r.label,
        r.min_age,
        r.max_age,
        r.notes,
      );
      rules += 1;
    }
  }

  return { products: raw.products.length, variants, rules };
}
