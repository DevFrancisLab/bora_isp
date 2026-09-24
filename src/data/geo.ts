import type { ServiceArea } from '../types';

/** Approximate Nairobi service areas. These are operational zones, not residential parcels. */
export const SERVICE_AREAS: ServiceArea[] = [
  {
    id: 'kilimani',
    name: 'Kilimani',
    polygon: [
      [-1.2852, 36.778],
      [-1.286, 36.7968],
      [-1.2935, 36.7992],
      [-1.3004, 36.794],
      [-1.2996, 36.7772],
      [-1.292, 36.7748],
    ],
  },
  {
    id: 'south-b',
    name: 'South B',
    polygon: [
      [-1.3055, 36.8225],
      [-1.3048, 36.8455],
      [-1.3135, 36.8488],
      [-1.3218, 36.841],
      [-1.3205, 36.824],
      [-1.312, 36.8208],
    ],
  },
  {
    id: 'lavington',
    name: 'Lavington',
    polygon: [
      [-1.2708, 36.7605],
      [-1.2715, 36.7795],
      [-1.2802, 36.7822],
      [-1.2884, 36.7768],
      [-1.2872, 36.759],
      [-1.278, 36.7568],
    ],
  },
  {
    id: 'kilimani-west',
    name: 'Kilimani West',
    polygon: [
      [-1.2888, 36.7555],
      [-1.2895, 36.7738],
      [-1.2978, 36.7755],
      [-1.3052, 36.7702],
      [-1.304, 36.7548],
      [-1.296, 36.7526],
    ],
  },
  {
    id: 'cbd',
    name: 'CBD',
    polygon: [
      [-1.2772, 36.8135],
      [-1.2766, 36.8318],
      [-1.2848, 36.8346],
      [-1.2922, 36.8288],
      [-1.291, 36.8142],
      [-1.2835, 36.811],
    ],
  },
];
