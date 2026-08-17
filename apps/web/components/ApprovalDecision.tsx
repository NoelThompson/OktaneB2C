'use client';

import { useState } from 'react';
import { Check, X, Loader2, CircleCheck, CircleX } from 'lucide-react';
import type { Order } from '@/lib/types';

/**
 * The approve/deny control.
 *
 * The one-time decision token issued by the step-up callback travels in the POST
 * body. Without it the agent refuses, which is what stops a forwarded link from
 * buying anything.
 */
export default function ApprovalDecision({
  approvalId,
  decisionToken,
}: {
  approvalId: string;
  decisionToken: string;
}) {
  const [busy, setBusy] = useState<'approve' | 'deny' | null>(null);
  const [outcome, setOutcome] = useState<
    { ok: true; state: string; order?: Order } | { ok: false; error: string } | null
  >(null);

  async function decide(decision: 'approve' | 'deny') {
    setBusy(decision);
    try {
      const response = await fetch(`/api/approvals/${approvalId}/decision`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ decision, decision_token: decisionToken }),
      });
      const body = await response.json();
      setOutcome(
        response.ok
          ? { ok: true, state: body.approval?.state, order: body.order }
          : { ok: false, error: body.detail ?? body.error ?? 'refused' },
      );
    } finally {
      setBusy(null);
    }
  }

  if (outcome?.ok) {
    const placed = outcome.state === 'COMPLETED';
    return (
      <div
        className={[
          'rounded-xl border p-4',
          placed
            ? 'border-success-green/40 bg-success-green/10'
            : 'border-neutral-border bg-primary/60',
        ].join(' ')}
      >
        <div className="flex items-center gap-2">
          {placed ? (
            <CircleCheck className="h-4 w-4 text-success-green" />
          ) : (
            <CircleX className="h-4 w-4 text-net-white/50" />
          )}
          <span className="text-sm font-semibold">
            {placed ? 'Purchase approved' : 'Purchase declined'}
          </span>
        </div>
        {outcome.order?.order_id && (
          <p className="mt-2 font-mono text-xs text-net-white/60">
            {outcome.order.order_id} · ${(outcome.order.total_cents / 100).toFixed(2)} ·
            placed for {outcome.order.subject} by {outcome.order.placed_by_agent}
          </p>
        )}
        <p className="mt-2.5 text-xs leading-relaxed text-net-white/50">
          You can close this tab — the storefront has already updated.
        </p>
      </div>
    );
  }

  return (
    <>
      {outcome && !outcome.ok && (
        <div className="mb-3 rounded-lg border border-error-red/40 bg-error-red/10 p-3 text-xs text-error-red">
          {outcome.error}
        </div>
      )}
      <div className="flex gap-3">
        <button
          type="button"
          disabled={busy !== null}
          onClick={() => decide('approve')}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-accent py-2.5 text-sm font-semibold text-neutral-bg hover:bg-accent-light disabled:opacity-50"
        >
          {busy === 'approve' ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Check className="h-4 w-4" />
          )}
          Approve purchase
        </button>
        <button
          type="button"
          disabled={busy !== null}
          onClick={() => decide('deny')}
          className="flex items-center justify-center gap-2 rounded-lg border border-neutral-border px-4 py-2.5 text-sm font-medium text-net-white/70 hover:border-error-red/50 hover:text-error-red disabled:opacity-50"
        >
          {busy === 'deny' ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <X className="h-4 w-4" />
          )}
          Decline
        </button>
      </div>
    </>
  );
}
