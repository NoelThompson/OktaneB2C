import { Clock, CircleCheck, Hourglass } from 'lucide-react';
import type { Intent } from '@/lib/types';
import { formatPrice } from '@/lib/format';

/**
 * Beat 5, rendered inline in the thread: the agent has recorded what to buy but
 * has bought nothing. The price is a ceiling, so a price rise fails rather than
 * quietly overspending.
 */
export default function PendingIntentCard({ intent }: { intent: Intent }) {
  const waiting = intent.state === 'PENDING_STOCK';
  const done = intent.state === 'COMPLETED';

  return (
    <div className="ml-11 max-w-md rounded-xl border border-accent/30 bg-accent/5 p-3.5">
      <div className="flex items-center gap-2">
        {done ? (
          <CircleCheck className="h-4 w-4 text-success-green" />
        ) : waiting ? (
          <Hourglass className="h-4 w-4 text-accent" />
        ) : (
          <Clock className="h-4 w-4 text-accent" />
        )}
        <span className="text-xs font-semibold uppercase tracking-[0.12em] text-accent">
          {done ? 'Order placed' : 'Standing order'}
        </span>
        <span className="ml-auto font-mono text-[10px] text-net-white/30">
          {intent.state}
        </span>
      </div>

      <div className="mt-2.5 text-sm font-medium">{intent.product_name}</div>
      <div className="text-xs text-net-white/50">
        {intent.variant_label} · qty {intent.qty} ·{' '}
        {formatPrice(intent.max_total_cents)} max
      </div>

      <p className="mt-2.5 text-[11px] leading-relaxed text-net-white/45">
        {done
          ? `Order ${intent.order_id} — released only after you approved it.`
          : 'Nothing has been bought. When stock returns, the assistant will ask you to approve the purchase.'}
      </p>
    </div>
  );
}
