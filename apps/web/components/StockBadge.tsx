import { Check, X, AlertTriangle } from 'lucide-react';

export default function StockBadge({ stock }: { stock: number }) {
  if (stock <= 0) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-error-red/15 px-2 py-0.5 text-[11px] font-medium text-error-red">
        <X className="h-3 w-3" />
        Out of stock
      </span>
    );
  }
  if (stock <= 5) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-accent/15 px-2 py-0.5 text-[11px] font-medium text-accent">
        <AlertTriangle className="h-3 w-3" />
        Only {stock} left
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-success-green/15 px-2 py-0.5 text-[11px] font-medium text-success-green">
      <Check className="h-3 w-3" />
      In stock
    </span>
  );
}
