'use client';

import { useState } from 'react';
import {
  Dribbble,
  Footprints,
  Target,
  Shirt,
  Wind,
  Backpack,
  Package,
  type LucideIcon,
} from 'lucide-react';
import type { Product } from '@/lib/types';
import { formatPrice } from '@/lib/format';
import StockBadge from './StockBadge';

const ICONS: Record<string, LucideIcon> = {
  Dribbble,
  Footprints,
  Target,
  Shirt,
  Wind,
  Backpack,
};

export default function ProductCard({ product }: { product: Product }) {
  const [selected, setSelected] = useState(product.variants[0].sku);
  const variant =
    product.variants.find((v) => v.sku === selected) ?? product.variants[0];
  const Icon = ICONS[product.icon] ?? Package;
  const multiSize = product.variants.length > 1;

  return (
    <article className="flex flex-col rounded-xl border border-neutral-border bg-primary/60 p-4 hover:border-accent/40">
      <div className="mb-3 flex h-28 items-center justify-center rounded-lg bg-gradient-to-br from-primary-light to-neutral-bg">
        <Icon className="h-12 w-12 text-accent" strokeWidth={1.25} />
      </div>

      <div className="text-[10px] uppercase tracking-[0.14em] text-net-white/35">
        {product.category}
      </div>
      <h3 className="mt-1 font-display text-sm font-semibold leading-snug">
        {product.name}
      </h3>
      <p className="mt-1.5 text-xs leading-relaxed text-net-white/50">
        {product.blurb}
      </p>

      {multiSize && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {product.variants.map((v) => {
            const active = v.sku === selected;
            const oos = v.stock <= 0;
            return (
              <button
                key={v.sku}
                type="button"
                onClick={() => setSelected(v.sku)}
                title={oos ? `${v.label} — out of stock` : v.label}
                className={[
                  'rounded-md border px-2 py-1 text-xs font-medium',
                  active
                    ? 'border-accent bg-accent/15 text-accent'
                    : 'border-neutral-border text-net-white/60 hover:border-accent/40',
                  oos ? 'line-through decoration-error-red/70' : '',
                ].join(' ')}
              >
                {v.size}
              </button>
            );
          })}
        </div>
      )}

      <div className="mt-auto pt-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="font-display text-base font-bold">
            {formatPrice(variant.price_cents)}
          </span>
          <StockBadge stock={variant.stock} />
        </div>
        <button
          type="button"
          disabled={variant.stock <= 0}
          className="w-full rounded-lg bg-accent py-2 text-sm font-semibold text-neutral-bg hover:bg-accent-light disabled:cursor-not-allowed disabled:bg-neutral-border disabled:text-net-white/40"
        >
          {variant.stock <= 0 ? 'Out of stock' : 'Add to cart'}
        </button>
      </div>
    </article>
  );
}
