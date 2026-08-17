/**
 * Oktane B2C MCP server — the resource server, live in the request path.
 *
 * Every tool call arrives as JSON-RPC 2.0 on POST /mcp and is authorized in
 * `auth.ts` before it can reach SQLite. The agent has no other way to the data.
 */

import express, { type Request, type Response } from 'express';
import { authorize, REQUIRE_AUTH } from './auth.ts';
import { TOOL_REQUIREMENTS } from './scopes.ts';
import * as catalog from './tools/catalog.ts';
import * as inventory from './tools/inventory.ts';
import * as orders from './tools/orders.ts';
import { OrderError } from './tools/orders.ts';
import { getDb } from './db.ts';

const PORT = Number(process.env.MCP_PORT ?? 8787);
const DEMO_MODE = process.env.DEMO_MODE !== 'off';

const app = express();
app.use(express.json({ limit: '256kb' }));

/** JSON-RPC error codes: -326xx is our application-defined range. */
const RPC = {
  parse: -32700,
  invalidRequest: -32600,
  methodNotFound: -32601,
  invalidParams: -32602,
  internal: -32603,
  unauthorized: -32001,
  forbidden: -32003,
  conflict: -32009,
} as const;

interface RpcRequest {
  jsonrpc?: string;
  id?: string | number | null;
  method?: string;
  params?: Record<string, unknown>;
}

function rpcError(
  res: Response,
  id: string | number | null,
  code: number,
  message: string,
  data?: unknown,
) {
  res.json({ jsonrpc: '2.0', id, error: { code, message, data } });
}

app.get('/healthz', (_req, res) => {
  const row = getDb().prepare('SELECT COUNT(*) AS n FROM products').get() as { n: number };
  res.json({ ok: true, require_auth: REQUIRE_AUTH, products: row.n });
});

/** Advertised tool surface, so the agent can discover scopes it must obtain. */
app.get('/mcp/tools', (_req, res) => {
  res.json({
    require_auth: REQUIRE_AUTH,
    tools: Object.entries(TOOL_REQUIREMENTS).map(([name, req]) => ({
      name,
      required_scope: req.scope,
      audience: req.audience,
    })),
  });
});

/**
 * Public product listing for the storefront tiles. Deliberately unauthenticated
 * — a real retailer's catalog page is public. The contrast matters: the agent
 * cannot use this path, because acting on a shopper's behalf requires a token.
 */
app.get('/public/catalog', (_req, res) => {
  res.json(catalog.search({ limit: 50 }));
});

/** Demo control plane: fire a restock so a standing intent can wake up. */
app.post('/demo/restock', (req, res) => {
  if (!DEMO_MODE) {
    res.status(404).json({ error: 'demo mode off' });
    return;
  }
  const { sku, stock } = req.body ?? {};
  if (typeof sku !== 'string') {
    res.status(400).json({ error: 'sku required' });
    return;
  }
  try {
    res.json(inventory.restock({ sku, stock: typeof stock === 'number' ? stock : 12 }));
  } catch (err) {
    res.status(400).json({ error: err instanceof Error ? err.message : String(err) });
  }
});

app.post('/mcp', async (req: Request, res: Response) => {
  const body = req.body as RpcRequest;
  const id = body?.id ?? null;

  if (body?.jsonrpc !== '2.0' || typeof body.method !== 'string') {
    rpcError(res, id, RPC.invalidRequest, 'expected JSON-RPC 2.0 with a method');
    return;
  }

  const tool = body.method;
  const params = body.params ?? {};

  const auth = await authorize(tool, req.header('authorization'));
  if (!auth.ok) {
    const code =
      auth.code === 'unknown_tool'
        ? RPC.methodNotFound
        : auth.code === 'missing_token' || auth.code === 'invalid_token'
          ? RPC.unauthorized
          : RPC.forbidden;
    console.warn(`[mcp] DENY ${tool}: ${auth.code} — ${auth.detail}`);
    rpcError(res, id, code, auth.code ?? 'denied', {
      reason: auth.code,
      detail: auth.detail,
      required: TOOL_REQUIREMENTS[tool] ?? null,
      presented_scopes: auth.scopes ?? [],
    });
    return;
  }

  const subject = auth.subject ?? 'unknown';
  console.log(`[mcp] ALLOW ${tool} sub=${subject} agent=${auth.actor ?? '-'}`);

  try {
    switch (tool) {
      case 'catalog.search':
        res.json({ jsonrpc: '2.0', id, result: catalog.search(params as never) });
        return;
      case 'catalog.sizing_guide':
        res.json({ jsonrpc: '2.0', id, result: catalog.sizingGuide(params as never) });
        return;
      case 'inventory.check':
        res.json({ jsonrpc: '2.0', id, result: inventory.check(params as never) });
        return;
      case 'orders.list':
        res.json({ jsonrpc: '2.0', id, result: orders.list({ subject }) });
        return;
      case 'orders.create':
        res.json({
          jsonrpc: '2.0',
          id,
          result: orders.create(params as never, { subject, agent: auth.actor }),
        });
        return;
      default:
        rpcError(res, id, RPC.methodNotFound, `unknown tool ${tool}`);
        return;
    }
  } catch (err) {
    if (err instanceof OrderError) {
      rpcError(res, id, RPC.conflict, err.code, { detail: err.message });
      return;
    }
    const message = err instanceof Error ? err.message : String(err);
    console.error(`[mcp] ERROR ${tool}: ${message}`);
    rpcError(res, id, RPC.internal, message);
  }
});

app.listen(PORT, () => {
  console.log(`[mcp] listening on http://localhost:${PORT}`);
  console.log(`[mcp] MCP_REQUIRE_AUTH=${REQUIRE_AUTH}`);
});
