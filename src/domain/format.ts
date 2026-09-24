export function uid(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 8)}${Date.now().toString(36).slice(-3)}`;
}

export function formatNumber(value: number) {
  return new Intl.NumberFormat('en-KE').format(value);
}

export function formatKes(value: number) {
  return `KSh ${new Intl.NumberFormat('en-KE').format(value)}`;
}

export function formatPhone(raw: string) {
  const digits = raw.replace(/\D/g, '');
  if (digits.startsWith('254') && digits.length >= 12) {
    return `+254 ${digits.slice(3, 6)} ${digits.slice(6, 9)} ${digits.slice(9, 12)}`;
  }
  return raw;
}

export function digitsOnly(value: string) {
  return value.replace(/\D/g, '');
}

export function timeAgo(iso: string) {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return hours === 1 ? '1 hour ago' : `${hours} hours ago`;
  const days = Math.round(hours / 24);
  return days === 1 ? 'Yesterday' : `${days} days ago`;
}

export function formatClock(iso: string) {
  return new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'Africa/Nairobi',
  }).format(new Date(iso));
}

export function formatDate(iso: string) {
  return new Intl.DateTimeFormat('en-KE', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'Africa/Nairobi',
  }).format(new Date(iso));
}

export function formatWhen(iso: string) {
  return `${formatDate(iso)} · ${formatClock(iso)}`;
}

/** Today at HH:mm in Africa/Nairobi (EAT, UTC+3). */
export function atNairobi(hours: number, minutes: number, dayOffset = 0) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Africa/Nairobi',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date());
  const year = Number(parts.find((part) => part.type === 'year')?.value);
  const month = Number(parts.find((part) => part.type === 'month')?.value);
  const day = Number(parts.find((part) => part.type === 'day')?.value);
  return new Date(Date.UTC(year, month - 1, day + dayOffset, hours - 3, minutes, 0)).toISOString();
}

export function minutesAgo(minutes: number) {
  return new Date(Date.now() - minutes * 60_000).toISOString();
}

export function onlinePercent(active: number, online: number) {
  if (active <= 0) return 0;
  return Math.round((online / active) * 1000) / 10;
}

export function titleCase(value: string) {
  return value.replace(/-/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}
