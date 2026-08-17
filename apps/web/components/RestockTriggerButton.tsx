'use client';

import { useState } from 'react';
import { PackagePlus, Loader2 } from 'lucide-react';

/** The one scripted event in the demo. Everything after it is the real code path. */
export default function RestockTriggerButton({
  onRestock,
}: {
  onRestock: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);

  return (
    <button
      type="button"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await onRestock();
        } finally {
          setBusy(false);
        }
      }}
      className="inline-flex items-center gap-2 rounded-lg border border-tech-purple/40 bg-tech-purple/10 px-3 py-1.5 text-xs font-medium text-tech-purple-light hover:bg-tech-purple/20 disabled:opacity-50"
      title="Demo trigger: put size 7 back in stock"
    >
      {busy ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <PackagePlus className="h-3.5 w-3.5" />
      )}
      Simulate restock
    </button>
  );
}
