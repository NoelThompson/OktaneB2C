'use client';

import { useState } from 'react';
import { ArrowUp } from 'lucide-react';

export default function ChatComposer({
  onSend,
  disabled,
  placeholder,
  suggestions = [],
}: {
  onSend: (message: string) => void;
  disabled: boolean;
  placeholder: string;
  suggestions?: string[];
}) {
  const [value, setValue] = useState('');

  function submit(text: string) {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    setValue('');
    onSend(trimmed);
  }

  return (
    <div className="border-t border-neutral-border bg-primary/60 px-4 py-3">
      {suggestions.length > 0 && (
        <div className="mb-2.5 flex flex-wrap gap-2">
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              disabled={disabled}
              onClick={() => submit(s)}
              className="rounded-full border border-neutral-border px-3 py-1.5 text-xs text-net-white/60 hover:border-accent/50 hover:text-accent disabled:opacity-40"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(value);
        }}
        className="flex items-end gap-2"
      >
        <textarea
          rows={1}
          value={value}
          disabled={disabled}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              submit(value);
            }
          }}
          placeholder={placeholder}
          className="max-h-32 flex-1 resize-none rounded-xl border border-neutral-border bg-neutral-bg/70 px-3.5 py-2.5 text-sm text-net-white placeholder:text-net-white/30 focus:border-accent/60 focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent text-neutral-bg hover:bg-accent-light disabled:cursor-not-allowed disabled:bg-neutral-border disabled:text-net-white/30"
          aria-label="Send"
        >
          <ArrowUp className="h-4 w-4" strokeWidth={2.5} />
        </button>
      </form>
    </div>
  );
}
