import { createSeed } from '../data/seed';
import type { OperationsSnapshot } from '../types';

/**
 * Data access boundary.
 * Pages read the operations store, never this module.
 * Replace this function with a Django client, for example GET /api/operations/snapshot/.
 */
export async function loadOperationsSnapshot(): Promise<OperationsSnapshot> {
  await new Promise((resolve) => window.setTimeout(resolve, 320));
  return createSeed();
}
