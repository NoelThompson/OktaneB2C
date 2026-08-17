import Storefront from '@/components/Storefront';
import { agentJson, getProfile } from '@/lib/agent';
import { getCatalog } from '@/lib/catalog';
import type { Profile } from '@/lib/types';

export const dynamic = 'force-dynamic';

export default async function HomePage() {
  const [products, profile, session] = await Promise.all([
    getCatalog(),
    getProfile(),
    agentJson<{ mock: boolean; shoppers: Profile[] }>('/auth/shoppers').catch(() => ({
      mock: false,
      shoppers: [] as Profile[],
    })),
  ]);

  return (
    <Storefront
      initialProducts={products}
      initialProfile={profile}
      shoppers={session.shoppers}
      demoMode={session.mock}
    />
  );
}
