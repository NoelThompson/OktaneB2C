import type { TraceEvent } from '@/lib/types';

/**
 * Decoded claims for one step in the chain.
 *
 * `sub` is the human and `act.sub` / `cid` is the agent. That contrast is the
 * whole "on behalf of" story in one screenshot, so those two rows are
 * highlighted and everything else is muted.
 */

const HUMAN_KEYS = new Set(['sub']);
const AGENT_KEYS = new Set(['act.sub', 'cid', 'client_id', 'placed_by_agent']);

function render(value: unknown): string {
  if (Array.isArray(value)) return value.join(' ');
  if (value === null || value === undefined) return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export default function TokenChip({ event }: { event: TraceEvent }) {
  const entries = Object.entries(event.claims ?? {});
  if (entries.length === 0) return null;

  const isToken =
    event.kind === 'id_jag' ||
    event.kind === 'access_token' ||
    event.kind === 'user_token';

  return (
    <div className="mt-2 rounded-md border border-tech-purple/25 bg-neutral-bg/70 p-2.5">
      <dl className="space-y-1">
        {entries.map(([key, value]) => {
          const human = HUMAN_KEYS.has(key);
          const agent = AGENT_KEYS.has(key);
          return (
            <div key={key} className="flex gap-2 font-mono text-[11px] leading-relaxed">
              <dt
                className={[
                  'w-[86px] shrink-0 text-right',
                  human
                    ? 'text-accent'
                    : agent
                      ? 'text-tech-purple-light'
                      : 'text-net-white/35',
                ].join(' ')}
              >
                {key}
              </dt>
              <dd
                className={[
                  'break-all',
                  human || agent ? 'text-net-white' : 'text-net-white/60',
                ].join(' ')}
              >
                {render(value)}
                {human && (
                  <span className="ml-1.5 text-[10px] text-accent/70">the shopper</span>
                )}
                {agent && (
                  <span className="ml-1.5 text-[10px] text-tech-purple-light/70">
                    the agent
                  </span>
                )}
              </dd>
            </div>
          );
        })}
      </dl>
      {isToken && (
        <div className="mt-2 border-t border-tech-purple/15 pt-1.5 font-mono text-[10px] text-net-white/25">
          signature verified, value elided
        </div>
      )}
    </div>
  );
}
