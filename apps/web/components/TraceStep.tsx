'use client';

import { useState } from 'react';
import {
  UserCheck,
  ArrowLeftRight,
  KeyRound,
  Database,
  ShieldAlert,
  Fingerprint,
  Info,
  ChevronRight,
  type LucideIcon,
} from 'lucide-react';
import type { TraceEvent, TraceKind } from '@/lib/types';
import TokenChip from './TokenChip';

const ICONS: Record<TraceKind, LucideIcon> = {
  user_token: UserCheck,
  id_jag: ArrowLeftRight,
  access_token: KeyRound,
  mcp_call: Database,
  mcp_denied: ShieldAlert,
  stepup: Fingerprint,
  note: Info,
};

export default function TraceStep({
  event,
  index,
}: {
  event: TraceEvent;
  index: number;
}) {
  const [open, setOpen] = useState(false);
  const Icon = ICONS[event.kind] ?? Info;
  const hasClaims = Object.keys(event.claims ?? {}).length > 0;

  return (
    <li className="relative pl-8">
      <span
        className={[
          'absolute left-0 top-0.5 flex h-6 w-6 items-center justify-center rounded-full border',
          event.ok
            ? 'border-tech-purple/40 bg-tech-purple/15 text-tech-purple-light'
            : 'border-error-red/50 bg-error-red/15 text-error-red',
        ].join(' ')}
      >
        <Icon className="h-3.5 w-3.5" />
      </span>

      <button
        type="button"
        onClick={() => hasClaims && setOpen(!open)}
        className={[
          'w-full text-left',
          hasClaims ? 'cursor-pointer' : 'cursor-default',
        ].join(' ')}
        aria-expanded={hasClaims ? open : undefined}
      >
        <div className="flex items-start gap-1.5">
          <span className="mt-px font-mono text-[10px] text-net-white/25">
            {String(index + 1).padStart(2, '0')}
          </span>
          <span
            className={[
              'text-xs font-medium leading-snug',
              event.ok ? 'text-net-white/90' : 'text-error-red',
            ].join(' ')}
          >
            {event.label}
          </span>
          {hasClaims && (
            <ChevronRight
              className={[
                'ml-auto mt-0.5 h-3.5 w-3.5 shrink-0 text-net-white/30 transition-transform',
                open ? 'rotate-90' : '',
              ].join(' ')}
            />
          )}
        </div>
        {event.detail && (
          <div className="mt-0.5 break-all font-mono text-[10px] leading-relaxed text-net-white/45">
            {event.detail}
          </div>
        )}
      </button>

      {open && <TokenChip event={event} />}
    </li>
  );
}
