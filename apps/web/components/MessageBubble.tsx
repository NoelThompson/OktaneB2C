import { Sparkles, User } from 'lucide-react';
import type { ChatMessage } from '@/lib/types';

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const mine = message.role === 'user';

  return (
    <div className={['flex gap-3', mine ? 'flex-row-reverse' : ''].join(' ')}>
      <div
        className={[
          'mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border',
          mine
            ? 'border-accent/40 bg-accent/15 text-accent'
            : 'border-okta-blue/40 bg-okta-blue/15 text-okta-blue-light',
        ].join(' ')}
      >
        {mine ? <User className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
      </div>

      <div
        className={[
          'max-w-[min(46rem,80%)] rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
          mine
            ? 'rounded-tr-sm bg-accent text-neutral-bg'
            : 'rounded-tl-sm border border-neutral-border bg-primary/70 text-net-white/90',
        ].join(' ')}
      >
        {message.pending ? (
          <span className="flex items-center gap-1.5 py-0.5">
            {[0, 150, 300].map((delay) => (
              <span
                key={delay}
                className="h-1.5 w-1.5 animate-bounce rounded-full bg-okta-blue-light/70"
                style={{ animationDelay: `${delay}ms` }}
              />
            ))}
            <span className="ml-1 text-xs text-net-white/40">{message.content}</span>
          </span>
        ) : (
          message.content.split('\n').map((line, i) =>
            line ? (
              <p key={i} className={i > 0 ? 'mt-2' : ''}>
                {line}
              </p>
            ) : null,
          )
        )}
      </div>
    </div>
  );
}
