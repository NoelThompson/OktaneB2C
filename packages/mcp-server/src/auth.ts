/**
 * Token verification for the MCP server.
 *
 * The MCP server is the resource server in the on-behalf-of flow. The agent
 * never touches the database directly; it must present an access token whose
 * audience and scope this file independently verifies against the issuer's
 * JWKS. Nothing here trusts the agent's word for anything.
 */

import { createRemoteJWKSet, jwtVerify, type JWTPayload } from 'jose';
import { requirementFor } from './scopes.ts';

export const REQUIRE_AUTH = process.env.MCP_REQUIRE_AUTH === 'true';

/**
 * In mock mode the agent mints its own RS256 tokens and serves the matching
 * JWKS, so the verification path below is exercised for real with zero Okta
 * dependency. Flipping to a real Okta issuer changes only these two vars.
 */
const CATALOG_ISSUER = process.env.OKTA_CATALOG_ISSUER ?? '';
const ORDERS_ISSUER = process.env.OKTA_ORDERS_ISSUER ?? '';

const jwksCache = new Map<string, ReturnType<typeof createRemoteJWKSet>>();

function jwksFor(issuer: string) {
  let jwks = jwksCache.get(issuer);
  if (!jwks) {
    jwks = createRemoteJWKSet(new URL(`${issuer}/v1/keys`), {
      cacheMaxAge: 10 * 60 * 1000,
    });
    jwksCache.set(issuer, jwks);
  }
  return jwks;
}

function issuerForAudience(audience: string): string {
  if (audience === (process.env.OKTA_ORDERS_AUDIENCE ?? 'api://oktane-orders')) {
    return ORDERS_ISSUER;
  }
  return CATALOG_ISSUER;
}

export interface AuthResult {
  ok: boolean;
  /** Machine-readable reason, surfaced to the telemetry drawer verbatim. */
  code?:
    | 'unknown_tool'
    | 'missing_token'
    | 'invalid_token'
    | 'wrong_audience'
    | 'insufficient_scope'
    | 'no_issuer_configured';
  detail?: string;
  claims?: JWTPayload;
  /** The human the agent is acting for. */
  subject?: string;
  /** The agent's own identity, from `cid` or the `act` claim. */
  actor?: string;
  scopes?: string[];
}

function scopesOf(claims: JWTPayload): string[] {
  const scp = (claims as Record<string, unknown>).scp;
  if (Array.isArray(scp)) return scp.map(String);
  const scope = (claims as Record<string, unknown>).scope;
  if (typeof scope === 'string') return scope.split(' ').filter(Boolean);
  return [];
}

/**
 * Read the `aud` claim WITHOUT verifying the signature. Used only to explain a
 * rejection that already happened — never to make an authorization decision.
 */
function peekAudience(token: string): string | undefined {
  try {
    const [, payload] = token.split('.');
    if (!payload) return undefined;
    const claims = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));
    const aud = claims?.aud;
    if (typeof aud === 'string') return aud;
    if (Array.isArray(aud) && typeof aud[0] === 'string') return aud[0];
  } catch {
    // A malformed token is just an invalid token; the caller reports that.
  }
  return undefined;
}

function actorOf(claims: JWTPayload): string | undefined {
  const act = (claims as Record<string, unknown>).act;
  if (act && typeof act === 'object' && 'sub' in act) {
    return String((act as Record<string, unknown>).sub);
  }
  const cid = (claims as Record<string, unknown>).cid;
  return typeof cid === 'string' ? cid : undefined;
}

/**
 * Authorize one tool call. Returns a structured result rather than throwing so
 * the server can put the reason on the wire — a denied call is a feature of
 * this demo, not an error to be swallowed.
 */
export async function authorize(
  tool: string,
  authorizationHeader: string | undefined,
): Promise<AuthResult> {
  const req = requirementFor(tool);
  if (!req) return { ok: false, code: 'unknown_tool', detail: tool };

  if (!REQUIRE_AUTH) {
    return { ok: true, subject: 'demo-unauthenticated', scopes: [req.scope] };
  }

  const token = authorizationHeader?.replace(/^Bearer\s+/i, '').trim();
  if (!token) {
    return {
      ok: false,
      code: 'missing_token',
      detail: `${tool} requires scope ${req.scope} for audience ${req.audience}`,
    };
  }

  const issuer = issuerForAudience(req.audience);
  if (!issuer) {
    return {
      ok: false,
      code: 'no_issuer_configured',
      detail: `no issuer configured for audience ${req.audience}`,
    };
  }

  let claims: JWTPayload;
  try {
    const verified = await jwtVerify(token, jwksFor(issuer), {
      issuer,
      audience: req.audience,
      clockTolerance: 5,
    });
    claims = verified.payload;
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    const presented = peekAudience(token);
    // Each authorization server signs with its own keys, so a token minted for
    // the wrong audience fails as an unknown key rather than an audience
    // mismatch. Report what actually happened — "no applicable key found" tells
    // a viewer nothing about why the call was refused.
    if (presented && presented !== req.audience) {
      return {
        ok: false,
        code: 'wrong_audience',
        detail: `token audience is ${presented}, this tool requires ${req.audience} (issued by a different authorization server)`,
      };
    }
    return { ok: false, code: 'invalid_token', detail: message };
  }

  const scopes = scopesOf(claims);
  if (!scopes.includes(req.scope)) {
    return {
      ok: false,
      code: 'insufficient_scope',
      detail: `${tool} requires ${req.scope}; token carries [${scopes.join(', ')}]`,
      claims,
      scopes,
    };
  }

  return {
    ok: true,
    claims,
    subject: typeof claims.sub === 'string' ? claims.sub : undefined,
    actor: actorOf(claims),
    scopes,
  };
}
