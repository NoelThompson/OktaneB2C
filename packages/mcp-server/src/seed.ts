import { seed, DB_PATH } from './db.ts';

const counts = seed();
console.log(`seeded ${DB_PATH}`);
console.log(
  `  products=${counts.products} variants=${counts.variants} sizing_rules=${counts.rules}`,
);
