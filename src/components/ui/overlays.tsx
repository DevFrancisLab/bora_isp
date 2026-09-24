import { useEffect, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { IconButton } from './primitives';

function useDismiss(open: boolean, onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeRef.current();
      if (event.key !== 'Tab' || !ref.current) return;
      const nodes = Array.from(ref.current.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')).filter(
        (node) => !node.hasAttribute('disabled'),
      );
      if (!nodes.length) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.setTimeout(() => {
      const preferred = ref.current?.querySelector<HTMLElement>('[data-autofocus]');
      (preferred ?? ref.current)?.focus();
    }, 10);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
      previous?.focus?.();
    };
  }, [open]);
  return ref;
}

export function Modal({
  open,
  title,
  onClose,
  children,
  description,
}: {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useDismiss(open, onClose);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4">
      <button type="button" className="absolute inset-0 bg-black/60" aria-label="Close dialog" onClick={onClose} />
      <div ref={ref} role="dialog" aria-modal="true" aria-labelledby="dialog-title" tabIndex={-1} className="modal-pop relative z-10 max-h-[90vh] w-full max-w-lg overflow-y-auto surface p-5 shadow-2xl">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 id="dialog-title" className="text-lg font-semibold">{title}</h2>
            {description ? <p className="mt-1 text-sm text-muted">{description}</p> : null}
          </div>
          <IconButton label="Close" onClick={onClose}><X size={16} /></IconButton>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Drawer({
  open,
  title,
  description,
  onClose,
  children,
  width = 'max-w-md',
}: {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
  width?: string;
}) {
  const ref = useDismiss(open, onClose);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button type="button" className="absolute inset-0 bg-black/60" aria-label="Close panel" onClick={onClose} />
      <div ref={ref} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} className={`drawer-in relative flex h-full w-full flex-col border-l border-line bg-sidebar shadow-2xl ${width}`}>
        <header className="flex items-start justify-between gap-3 border-b border-line px-4 py-4">
          <div>
            <h2 className="text-lg font-semibold">{title}</h2>
            {description ? <p className="mt-1 text-sm text-muted">{description}</p> : null}
          </div>
          <IconButton label="Close" onClick={onClose}><X size={16} /></IconButton>
        </header>
        <div className="flex-1 overflow-y-auto p-4">{children}</div>
      </div>
    </div>
  );
}
