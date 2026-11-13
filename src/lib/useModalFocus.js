import { useEffect, useRef } from 'react';

/** A modal dialog's keyboard: focus on open, Escape closes, Tab stays inside, focus returns on close (to what had it,
 * else returnFocus, the account button that is still mounted). */
export function useModalFocus(open, panel, onClose, returnFocus) {
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  useEffect(() => {
    if (!open) return undefined;
    const fallbackFocus = returnFocus?.current;
    const before = document.activeElement;
    panel.current?.focus();
    const onKey = (e) => {
      if (e.key === 'Escape') { onCloseRef.current(); return; }
      if (e.key !== 'Tab' || !panel.current) return;
      const items = [...panel.current.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')]
        .filter((el) => !el.disabled && el.offsetParent !== null);
      if (!items.length) return;
      const first = items[0], last = items[items.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      const target = before && document.contains(before) ? before : fallbackFocus;
      if (target && typeof target.focus === 'function') target.focus();
    };
  }, [open, panel, returnFocus]);
}
