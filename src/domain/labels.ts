import type { AreaId, Channel, PayMethod } from '../types';

export const AREA_LABEL: Record<AreaId, string> = {
  kilimani: 'Kilimani',
  'south-b': 'South B',
  lavington: 'Lavington',
  'kilimani-west': 'Kilimani West',
  cbd: 'CBD',
};

export const CHANNEL_LABEL: Record<Channel, string> = {
  whatsapp: 'WhatsApp',
  voice: 'Voice',
  ussd: 'USSD',
  sms: 'SMS',
};

export const METHOD_LABEL: Record<PayMethod, string> = {
  mpesa: 'M-Pesa',
  bank: 'Bank',
  card: 'Card',
};

export const ISSUES = ['Internet Down', 'Slow Internet', 'Connection Unstable'] as const;

type Tone = 'brand' | 'warn' | 'crit' | 'info' | 'neutral';

const TONE: Record<string, Tone> = {
  active: 'brand',
  online: 'brand',
  operational: 'brand',
  resolved: 'brand',
  acknowledged: 'brand',
  paid: 'brand',
  connected: 'brand',
  suspended: 'crit',
  offline: 'crit',
  outage: 'crit',
  failed: 'crit',
  critical: 'crit',
  high: 'crit',
  pending: 'warn',
  unstable: 'warn',
  degraded: 'warn',
  investigating: 'warn',
  monitoring: 'warn',
  warning: 'warn',
  medium: 'warn',
  overdue: 'warn',
  open: 'info',
  assigned: 'info',
  info: 'info',
  low: 'neutral',
  inactive: 'neutral',
};

export function toneFor(value: string): Tone {
  return TONE[value] ?? 'neutral';
}

export const TONE_CLASS: Record<Tone, string> = {
  brand: 'bg-brand/15 text-brand',
  warn: 'bg-warn/15 text-warn',
  crit: 'bg-crit/15 text-crit',
  info: 'bg-info/15 text-info',
  neutral: 'bg-white/5 text-muted',
};
