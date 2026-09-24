import type { ButtonHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react';
import { titleCase as labelize } from '../../domain/format';
import { TONE_CLASS, toneFor } from '../../domain/labels';

export function cn(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(' ');
}

export function Button({
  variant = 'secondary',
  size = 'md',
  className,
  type = 'button',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'danger' | 'ghost'; size?: 'sm' | 'md' }) {
  return (
    <button
      type={type}
      className={cn('btn', variant === 'primary' && 'btn-primary', variant === 'secondary' && 'btn-secondary', variant === 'danger' && 'btn-danger', variant === 'ghost' && 'btn-ghost', size === 'sm' && 'px-2.5 py-1.5 text-xs', className)}
      {...props}
    />
  );
}

export function IconButton({ label, className, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button type="button" aria-label={label} title={label} className={cn('grid h-9 w-9 place-items-center rounded-lg text-muted hover:bg-elevated hover:text-ink', className)} {...props}>
      {children}
    </button>
  );
}

export function Badge({ value }: { value: string }) {
  return <span className={cn('badge', TONE_CLASS[toneFor(value)])}>{labelize(value)}</span>;
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block text-sm">
      <span className="mb-1.5 block text-muted">{label}</span>
      {children}
      {hint ? <span className="mt-1 block text-xs text-faint">{hint}</span> : null}
    </label>
  );
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cn('input', props.className)} />;
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="surface px-6 py-10 text-center">
      <h3 className="text-base font-semibold">{title}</h3>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted">{body}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  title = 'Unable to load network data',
  body = 'The operations feed did not respond. Your local session is unchanged.',
  onRetry,
}: {
  title?: string;
  body?: string;
  onRetry: () => void;
}) {
  return (
    <div role="alert" className="surface px-6 py-12 text-center">
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted">{body}</p>
      <Button className="mt-4" variant="primary" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('skeleton', className)} />;
}
