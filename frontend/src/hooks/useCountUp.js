import { useEffect, useRef, useState } from "react";

/**
 * useCountUp — animates a numeric value from 0 up to `target` on mount only.
 * Subsequent changes to `target` snap instantly (no re-animation on every re-render).
 *
 * Respects prefers-reduced-motion: returns the final value immediately.
 *
 * @param {number} target — the final value to count up to
 * @param {number} [duration=600] — animation duration in ms
 * @returns {number} — the current displayed value (integer)
 */
export default function useCountUp(target, duration = 600) {
  const numericTarget = Number.isFinite(target) ? target : 0;
  const firstSeenRef = useRef(null);
  const rafRef = useRef(null);
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    // Only animate the first time we see a non-zero target.
    if (firstSeenRef.current !== null) {
      setDisplay(numericTarget);
      return undefined;
    }

    if (numericTarget === 0) {
      // Don't animate from/to 0 — keep waiting until a real value arrives.
      setDisplay(0);
      return undefined;
    }

    // Respect reduced-motion
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    firstSeenRef.current = numericTarget;

    if (reduced) {
      setDisplay(numericTarget);
      return undefined;
    }

    const startTs = performance.now();
    const from = 0;
    const to = numericTarget;

    const tick = (now) => {
      const elapsed = now - startTs;
      const t = Math.min(1, elapsed / duration);
      // easeOutQuad
      const eased = 1 - (1 - t) * (1 - t);
      const value = Math.round(from + (to - from) * eased);
      setDisplay(value);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      }
    };
    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [numericTarget]);

  return display;
}
