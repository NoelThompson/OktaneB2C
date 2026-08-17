import Link from 'next/link';
import { ShieldCheck, Fingerprint, TriangleAlert, ArrowLeft } from 'lucide-react';
import ApprovalDecision from '@/components/ApprovalDecision';
import { AGENT_URL, agentJson } from '@/lib/agent';
import { formatPrice } from '@/lib/format';
import type { Approval, Intent } from '@/lib/types';

export const dynamic = 'force-dynamic';

/**
 * Where the shopper lands after step-up.
 *
 * Reached only through `/auth/stepup/callback`, which verifies PKCE, the bound
 * state, the subject, the nonce, `acr`, and `auth_time` freshness before it
 * hands this page a one-time decision token. Landing here without that token
 * shows the state but offers no way to release the order.
 */
export default async function ApprovePage({
  params,
  searchParams,
}: {
  params: Promise<{ approvalId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { approvalId } = await params;
  const query = await searchParams;
  const one = (key: string) => {
    const value = query[key];
    return Array.isArray(value) ? value[0] : value;
  };

  const decisionToken = one('dt');
  const error = one('error');
  const detail = one('detail');
  const retry = one('retry');

  const data = await agentJson<{ approval: Approval; intent: Intent | null }>(
    `/approvals/${encodeURIComponent(approvalId)}`,
  ).catch(() => null);

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6 py-12">
      <div className="mb-6 flex items-center gap-2.5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent">
          <span className="font-display text-lg font-extrabold text-neutral-bg">C</span>
        </div>
        <div className="font-display text-lg font-extrabold tracking-tight">
          Court<span className="text-accent">Edge</span>
        </div>
        <span className="ml-auto inline-flex items-center gap-1.5 rounded-full border border-okta-blue/30 bg-okta-blue/10 px-3 py-1.5 text-xs text-okta-blue-light">
          <ShieldCheck className="h-3.5 w-3.5" />
          Verified by Okta
        </span>
      </div>

      <div className="rounded-2xl border border-neutral-border bg-primary/60 p-5">
        {error ? (
          <>
            <div className="flex items-center gap-2 text-error-red">
              <TriangleAlert className="h-4 w-4" />
              <h1 className="font-display text-base font-semibold">
                We could not verify that it was you
              </h1>
            </div>
            <p className="mt-2 font-mono text-xs text-net-white/50">
              {error}
              {detail ? ` — ${detail}` : ''}
            </p>
            <p className="mt-3 text-xs leading-relaxed text-net-white/60">
              Nothing was purchased. Approving a purchase needs a second factor, and
              the check failed closed rather than guessing.
            </p>
            {retry && (
              <a
                href={`${AGENT_URL}/auth/stepup/start?approval_id=${encodeURIComponent(
                  approvalId,
                )}&code=${encodeURIComponent(retry)}`}
                className="mt-4 inline-flex items-center gap-2 rounded-lg bg-okta-blue px-3.5 py-2 text-sm font-semibold text-net-white hover:bg-okta-blue-light"
              >
                <Fingerprint className="h-4 w-4" />
                Try again
              </a>
            )}
          </>
        ) : data === null ? (
          <p className="text-sm text-net-white/60">
            We could not find that approval. It may have expired.
          </p>
        ) : (
          <>
            <div className="text-[10px] uppercase tracking-[0.14em] text-net-white/35">
              Approval requested
            </div>
            <h1 className="mt-1 font-display text-lg font-bold">
              {data.intent?.product_name ?? 'Purchase'}
            </h1>
            {data.intent && (
              <p className="mt-0.5 text-sm text-net-white/60">
                {data.intent.variant_label} · qty {data.intent.qty} ·{' '}
                {formatPrice(data.intent.max_total_cents)}
              </p>
            )}

            <dl className="mt-4 space-y-1.5 border-t border-neutral-border pt-3 font-mono text-[11px]">
              {[
                ['state', data.approval.state],
                ['acr', data.approval.verified_acr ?? '—'],
                [
                  'auth_time',
                  data.approval.verified_auth_time
                    ? new Date(data.approval.verified_auth_time * 1000).toISOString()
                    : '—',
                ],
                ['expires in', `${data.approval.seconds_remaining}s`],
              ].map(([key, value]) => (
                <div key={key} className="flex gap-3">
                  <dt className="w-[74px] shrink-0 text-right text-net-white/35">
                    {key}
                  </dt>
                  <dd className="text-net-white/70">{value}</dd>
                </div>
              ))}
            </dl>

            <div className="mt-5">
              {decisionToken ? (
                <ApprovalDecision
                  approvalId={approvalId}
                  decisionToken={decisionToken}
                />
              ) : data.approval.state === 'COMPLETED' ? (
                <p className="text-sm text-success-green">
                  Already approved — order {data.approval.order_id}.
                </p>
              ) : (
                <p className="text-xs leading-relaxed text-net-white/50">
                  This link on its own cannot approve a purchase. Open the notification
                  from the storefront so we can verify a second factor first.
                </p>
              )}
            </div>
          </>
        )}
      </div>

      <Link
        href="/"
        className="mt-5 inline-flex items-center gap-1.5 text-xs text-net-white/40 hover:text-net-white"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to the store
      </Link>
    </main>
  );
}
