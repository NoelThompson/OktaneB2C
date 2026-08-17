import type { Product } from '@/lib/types';
import ProductCard from './ProductCard';

export default function ProductGrid({
  products,
  children,
}: {
  products: Product[];
  children?: React.ReactNode;
}) {
  return (
    <section>
      <div className="mb-4 flex items-center gap-3">
        <h2 className="font-display text-xl font-bold tracking-tight">Shop the court</h2>
        <span className="text-xs text-net-white/40">{products.length} products</span>
        {children && <div className="ml-auto">{children}</div>}
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {products.map((p) => (
          <ProductCard key={p.sku} product={p} />
        ))}
      </div>
    </section>
  );
}
