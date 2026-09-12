import { motion, type Variants } from "framer-motion";
import type { ReactNode } from "react";
import { usePrefersReducedMotion } from "./hooks";

/** Section wrapper: consistent rhythm, and a reveal that respects reduced motion. */
export function Section({
  id, children, className = "", label, title, lead,
}: {
  id?: string; children?: ReactNode; className?: string;
  label?: string; title?: ReactNode; lead?: ReactNode;
}) {
  return (
    <section id={id} className={`relative py-20 sm:py-28 ${className}`}>
      <div className="container-x">
        {(label || title || lead) && (
          <Reveal className="mb-12 max-w-3xl">
            {label && <div className="label mb-4">{label}</div>}
            {title && <h2 className="text-headline font-extrabold">{title}</h2>}
            {lead && <p className="mt-4 text-base leading-relaxed text-muted sm:text-lg">{lead}</p>}
          </Reveal>
        )}
        {children}
      </div>
    </section>
  );
}

export const revealVariants: Variants = {
  hidden: { opacity: 0, y: 16 },
  show: (i: number = 0) => ({
    opacity: 1, y: 0,
    transition: { duration: 0.5, delay: i * 0.06, ease: [0.22, 1, 0.36, 1] },
  }),
};

export function Reveal({
  children, className = "", delay = 0, as = "div",
}: { children: ReactNode; className?: string; delay?: number; as?: "div" | "li" }) {
  const reduced = usePrefersReducedMotion();
  const Cmp = as === "li" ? motion.li : motion.div;
  if (reduced) return <Cmp className={className}>{children}</Cmp>;
  return (
    <Cmp
      className={className}
      variants={revealVariants}
      custom={delay}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-10% 0px" }}
    >
      {children}
    </Cmp>
  );
}

/** Small status dot that pulses only when live. */
export function StatusDot({ tone = "accent", live = true }: { tone?: string; live?: boolean }) {
  return (
    <span className="relative inline-flex h-2 w-2 shrink-0">
      {live && (
        <span className={`absolute inline-flex h-full w-full rounded-full bg-${tone} opacity-60 animate-pulse-dot`} />
      )}
      <span className={`relative inline-flex h-2 w-2 rounded-full bg-${tone}`} />
    </span>
  );
}

export function Pill({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-pill border px-2.5 py-1
                      font-mono text-[10px] uppercase tracking-[0.14em] ${className}`}>
      {children}
    </span>
  );
}
