import { loadApiSnapshot } from './adapt';
import type { OperationsSnapshot } from '../types';

/**
 * Operations data boundary.
 * Pages read the store. This module loads Django REST data and maps it
 * into the dashboard model. Plans, payments, and settings stay in the
 * local catalog because those APIs are not part of this milestone.
 */
export async function loadOperationsSnapshot(): Promise<OperationsSnapshot> {
  return loadApiSnapshot();
}
