/**
 * Tool -> required scope, and scope -> owning authorization server.
 *
 * This map is the enforcement point that makes the demo's API Access Management
 * story real: a token minted for the catalog authorization server cannot reach
 * `orders.create`, because that tool demands `orders:write` from a different
 * audience.
 */

export const CATALOG_AUDIENCE = process.env.OKTA_CATALOG_AUDIENCE ?? 'api://oktane-catalog';
export const ORDERS_AUDIENCE = process.env.OKTA_ORDERS_AUDIENCE ?? 'api://oktane-orders';

export interface ToolRequirement {
  scope: string;
  audience: string;
}

export const TOOL_REQUIREMENTS: Record<string, ToolRequirement> = {
  'catalog.search': { scope: 'catalog:read', audience: CATALOG_AUDIENCE },
  'catalog.sizing_guide': { scope: 'catalog:read', audience: CATALOG_AUDIENCE },
  'inventory.check': { scope: 'inventory:read', audience: CATALOG_AUDIENCE },
  'orders.list': { scope: 'orders:read', audience: ORDERS_AUDIENCE },
  'orders.create': { scope: 'orders:write', audience: ORDERS_AUDIENCE },
};

export function requirementFor(tool: string): ToolRequirement | undefined {
  return TOOL_REQUIREMENTS[tool];
}
