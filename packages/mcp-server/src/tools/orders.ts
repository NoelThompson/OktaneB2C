import { randomUUID } from 'node:crypto';
import { getDb } from '../db.ts';

export interface OrderRow {
  order_id: string;
  subject: string;
  variant_sku: string;
  qty: number;
  unit_cents: number;
  total_cents: number;
  placed_by_agent: string | null;
  approval_id: string | null;
  created_at: string;
}

export interface CreateArgs {
  variant_sku: string;
  qty?: number;
  /** Ceiling in cents the shopper approved; a price rise must not slip through. */
  max_total_cents?: number;
  approval_id?: string;
  idempotency_key?: string;
}

export interface CreateContext {
  /** The human whose behalf this is on, from the verified token's `sub`. */
  subject: string;
  /** The agent's own identity, from `act.sub` or `cid`. */
  agent?: string;
}

export type OrderErrorCode = 'unknown_variant' | 'out_of_stock' | 'price_exceeded';

export class OrderError extends Error {
  code: OrderErrorCode;

  constructor(code: OrderErrorCode, message: string) {
    super(message);
    this.code = code;
  }
}

/**
 * Place an order. Decrements stock and inserts the order in one transaction,
 * and treats a repeated `idempotency_key` as a no-op returning the original —
 * a double-clicked approval must not buy two basketballs.
 */
export function create(
  args: CreateArgs,
  ctx: CreateContext,
): { order: OrderRow; idempotent_replay: boolean } {
  const d = getDb();
  const qty = Math.max(1, args.qty ?? 1);

  if (args.idempotency_key) {
    const existing = d
      .prepare('SELECT * FROM orders WHERE idempotency_key = ?')
      .get(args.idempotency_key) as unknown as OrderRow | undefined;
    if (existing) return { order: existing, idempotent_replay: true };
  }

  const variant = d
    .prepare('SELECT sku, price_cents, stock FROM variants WHERE sku = ?')
    .get(args.variant_sku) as unknown as
    | { sku: string; price_cents: number; stock: number }
    | undefined;

  if (!variant) {
    throw new OrderError('unknown_variant', `unknown variant ${args.variant_sku}`);
  }
  if (variant.stock < qty) {
    throw new OrderError(
      'out_of_stock',
      `${args.variant_sku} has ${variant.stock} in stock, need ${qty}`,
    );
  }

  const total = variant.price_cents * qty;
  if (typeof args.max_total_cents === 'number' && total > args.max_total_cents) {
    throw new OrderError(
      'price_exceeded',
      `total ${total} exceeds approved ceiling ${args.max_total_cents}`,
    );
  }

  const order: OrderRow = {
    order_id: `ord_${randomUUID().slice(0, 12)}`,
    subject: ctx.subject,
    variant_sku: variant.sku,
    qty,
    unit_cents: variant.price_cents,
    total_cents: total,
    placed_by_agent: ctx.agent ?? null,
    approval_id: args.approval_id ?? null,
    created_at: new Date().toISOString(),
  };

  d.exec('BEGIN IMMEDIATE');
  try {
    const updated = d
      .prepare('UPDATE variants SET stock = stock - ? WHERE sku = ? AND stock >= ?')
      .run(qty, variant.sku, qty);
    if (updated.changes !== 1) {
      throw new OrderError('out_of_stock', `${args.variant_sku} went out of stock`);
    }

    d.prepare(
      `INSERT INTO orders (order_id, subject, variant_sku, qty, unit_cents,
                           total_cents, placed_by_agent, approval_id,
                           idempotency_key, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).run(
      order.order_id,
      order.subject,
      order.variant_sku,
      order.qty,
      order.unit_cents,
      order.total_cents,
      order.placed_by_agent,
      order.approval_id,
      args.idempotency_key ?? null,
      order.created_at,
    );
    d.exec('COMMIT');
  } catch (err) {
    d.exec('ROLLBACK');
    throw err;
  }

  return { order, idempotent_replay: false };
}

/** Orders belong to the token's subject; callers cannot ask for someone else's. */
export function list(ctx: { subject: string }): { orders: OrderRow[] } {
  const orders = getDb()
    .prepare(
      `SELECT o.*, p.name AS product_name, v.label AS variant_label
         FROM orders o
         JOIN variants v ON v.sku = o.variant_sku
         JOIN products p ON p.sku = v.product_sku
        WHERE o.subject = ?
        ORDER BY o.created_at DESC`,
    )
    .all(ctx.subject) as unknown as OrderRow[];
  return { orders };
}
