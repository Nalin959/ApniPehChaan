import { useEffect, useRef, useState } from "react";

/** True once the element has entered the viewport. Fires once, then disconnects. */
export function useInViewOnce<T extends Element>(rootMargin = "-12% 0px") {
  const ref = useRef<T | null>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || seen) return;
    const io = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setSeen(true); io.disconnect(); } },
      { rootMargin },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [seen, rootMargin]);
  return { ref, seen };
}

/** Respects the OS reduced-motion setting, and keeps respecting it if it changes. */
export function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(
    () => typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setReduced(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return reduced;
}

/**
 * Counts up to `target` once visible.
 *
 * Eased rather than linear, because a linear counter reads as a loading bar.
 * With reduced motion the final value is shown immediately — the number is the
 * information, the animation is not.
 */
export function useCountUp(target: number, duration = 1100) {
  const { ref, seen } = useInViewOnce<HTMLSpanElement>();
  const reduced = usePrefersReducedMotion();
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (!seen) return;
    if (reduced) { setValue(target); return; }
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setValue(Math.round(target * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [seen, target, duration, reduced]);

  return { ref, value };
}

/** Locks body scroll — used by the mobile menu so the page behind cannot move. */
export function useScrollLock(locked: boolean) {
  useEffect(() => {
    if (!locked) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, [locked]);
}

/** Window scrollY past a threshold — drives the navbar's scrolled state. */
export function useScrolled(threshold = 12) {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > threshold);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, [threshold]);
  return scrolled;
}
