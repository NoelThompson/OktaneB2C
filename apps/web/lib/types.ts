/** Shapes returned by the agent service. Kept aligned with `*.public()` in Python. */

export interface Variant {
  sku: string;
  size: string;
  label: string;
  price_cents: number;
  stock: number;
}

export interface Product {
  sku: string;
  name: string;
  category: string;
  icon: string;
  price_cents: number;
  blurb: string;
  sizing_guide?: string | null;
  variants: Variant[];
}

export interface Profile {
  sub: string;
  name: string;
  email: string;
}

export type ApprovalState =
  | 'PENDING_STOCK'
  | 'REQUESTED'
  | 'NOTIFIED'
  | 'STEPUP_STARTED'
  | 'STEPUP_VERIFIED'
  | 'APPROVED'
  | 'EXECUTING'
  | 'COMPLETED'
  | 'STEPUP_FAILED'
  | 'DENIED'
  | 'EXPIRED'
  | 'FAILED';

export interface Intent {
  intent_id: string;
  variant_sku: string;
  product_name: string;
  variant_label: string;
  qty: number;
  unit_cents: number;
  max_total_cents: number;
  state: string;
  approval_id: string | null;
  order_id: string | null;
  created_at: number;
  updated_at: number;
  history: string[];
}

export interface Approval {
  approval_id: string;
  intent_id: string;
  state: ApprovalState;
  created_at: number;
  expires_at: number;
  updated_at: number;
  seconds_remaining: number;
  verified_acr: string | null;
  verified_auth_time: number | null;
  failure: string | null;
  order_id: string | null;
  history: string[];
}

export type TraceKind =
  | 'user_token'
  | 'id_jag'
  | 'access_token'
  | 'mcp_call'
  | 'mcp_denied'
  | 'stepup'
  | 'note';

/** One row in the security telemetry trace. */
export interface TraceEvent {
  kind: TraceKind;
  label: string;
  detail: string;
  ok: boolean;
  claims: Record<string, unknown>;
  at: number;
}

export interface ChatTurn {
  reply: string;
  kind: string;
  intent: Intent | null;
  pending_intents: Intent[];
  trace: TraceEvent[];
  llm: 'anthropic' | 'deterministic';
  profile: Profile;
}

export interface Order {
  order_id: string;
  subject: string;
  variant_sku: string;
  qty: number;
  unit_cents: number;
  total_cents: number;
  placed_by_agent: string | null;
  approval_id: string | null;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  pending?: boolean;
  intent?: Intent | null;
}
