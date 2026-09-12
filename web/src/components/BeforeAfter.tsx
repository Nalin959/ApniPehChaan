import { motion } from "framer-motion";
import {
  ArrowDown, ArrowRight, Check, Database, Eye, History, ListFilter, RadioTower, Shuffle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useInViewOnce, usePrefersReducedMotion } from "../lib/hooks";
import { Reveal, Section } from "../lib/ui";

interface ScatterItem {
  /** Rendered in danger mono ahead of the label when present. */
  count?: string;
  label: string;
  /** Fixed, hand-picked disorder — deterministic so the layout never jitters between renders. */
  rotate: number;
  x: number;
  y: number;
  drift: number;
}

const BEFORE: ScatterItem[] = [
  { count: "14", label: "sources",          rotate: -6.5, x: -12, y: 4,  drift: 3.2 },
  { count: "6",  label: "data brokers",     rotate: 4.5,  x: 14,  y: -6, drift: 4.1 },
  { count: "3",  label: "public profiles",  rotate: -3,   x: -8,  y: 12, drift: 2.8 },
  { count: "2",  label: "breach records",   rotate: 7,    x: 10,  y: 2,  drift: 3.7 },
  { label: "Multiple unknown sources",      rotate: -4.5, x: -4,  y: 16, drift: 4.6 },
];

const AFTER: { label: string; Icon: LucideIcon }[] = [
  { label: "Centralised visibility",  Icon: Eye },
  { label: "Removal requests",        Icon: Database },
  { label: "Risk prioritisation",     Icon: ListFilter },
  { label: "Continuous monitoring",   Icon: RadioTower },
  { label: "Activity history",        Icon: History },
];

export interface BeforeAfterProps {
  id?: string;
  className?: string;
}

export function BeforeAfter({ id = "clarity", className = "" }: BeforeAfterProps) {
  const reduced = usePrefersReducedMotion();
  const { ref, seen } = useInViewOnce<HTMLDivElement>();
  const show = seen || reduced;

  return (
    <Section
      id={id}
      className={className}
      label="Before / after"
      title="Scattered everywhere. Or accounted for."
      lead="The information itself does not change. What changes is whether you can see all of it in one place and do something about it."
    >
      <div
        ref={ref}
        className="grid items-stretch gap-5 lg:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] lg:gap-6"
      >
        {/* ------------------------------------------------------------- */}
        {/* BEFORE — disorder                                              */}
        {/* ------------------------------------------------------------- */}
        <Reveal className="h-full">
          <section
            aria-labelledby={`${id}-before`}
            className="relative flex h-full flex-col overflow-hidden rounded-card border border-danger/25
                       bg-danger/[0.035] p-5 sm:p-7"
          >
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 opacity-40
                         bg-[repeating-linear-gradient(115deg,rgb(var(--danger)/0.06)_0_1px,transparent_1px_9px)]"
            />
            <div className="relative flex items-center justify-between gap-3">
              <span className="mono text-[10px] uppercase tracking-[0.2em] text-danger/80">Before</span>
              <Shuffle className="h-3.5 w-3.5 text-danger/60" aria-hidden="true" />
            </div>

            <h3 id={`${id}-before`} className="relative mt-4 text-lg font-bold tracking-tight text-text sm:text-xl">
              Your information is scattered across:
            </h3>

            <ul className="relative mt-7 flex flex-1 flex-wrap content-center items-center justify-center gap-x-3 gap-y-4 py-2">
              {BEFORE.map((item, i) => {
                const settled = {
                  opacity: 1,
                  rotate: item.rotate,
                  x: item.x,
                  y: item.y,
                };
                return (
                  <motion.li
                    key={item.label}
                    className="max-w-full"
                    initial={reduced ? false : { opacity: 0, rotate: 0, x: 0, y: 0 }}
                    animate={
                      show
                        ? reduced
                          ? settled
                          : {
                              ...settled,
                              // Never quite still: the point of this side is
                              // that nothing here is under control.
                              y: [item.y, item.y - item.drift, item.y],
                            }
                        : undefined
                    }
                    transition={
                      reduced
                        ? { duration: 0 }
                        : {
                            default: { duration: 0.55, delay: 0.07 * i, ease: [0.22, 1, 0.36, 1] },
                            y: { duration: 3.4 + i * 0.35, repeat: Infinity, ease: "easeInOut", delay: 0.07 * i },
                          }
                    }
                  >
                    <span
                      className="inline-flex max-w-full items-center gap-2 rounded-pill border border-danger/30
                                 bg-bg/70 px-3.5 py-2 backdrop-blur-[2px]"
                    >
                      {item.count && (
                        <span className="mono text-sm font-bold text-danger">{item.count}</span>
                      )}
                      <span className="truncate text-xs text-muted sm:text-[13px]">{item.label}</span>
                    </span>
                  </motion.li>
                );
              })}
            </ul>

            <p className="relative mt-6 text-[11px] leading-relaxed text-faint">
              No single view, no record of what you asked for, nothing watching for the next listing.
            </p>
          </section>
        </Reveal>

        {/* ------------------------------------------------------------- */}
        {/* The turn                                                       */}
        {/* ------------------------------------------------------------- */}
        <div className="flex items-center justify-center lg:flex-col" aria-hidden="true">
          <span className="h-px flex-1 bg-gradient-to-r from-transparent to-border-strong lg:h-auto lg:w-px lg:flex-1 lg:bg-gradient-to-b" />
          <span className="mx-4 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-accent/40 bg-elevated text-accent shadow-glow-sm lg:mx-0 lg:my-4">
            <ArrowRight className="hidden h-4 w-4 lg:block" strokeWidth={2} />
            <ArrowDown className="h-4 w-4 lg:hidden" strokeWidth={2} />
          </span>
          <span className="h-px flex-1 bg-gradient-to-l from-transparent to-border-strong lg:h-auto lg:w-px lg:flex-1 lg:bg-gradient-to-t" />
        </div>

        {/* ------------------------------------------------------------- */}
        {/* AFTER — order                                                  */}
        {/* ------------------------------------------------------------- */}
        <Reveal delay={1} className="h-full">
          <section
            aria-labelledby={`${id}-after`}
            className="relative flex h-full flex-col overflow-hidden rounded-card border border-accent/25
                       bg-accent/[0.035] p-5 shadow-lift sm:p-7"
          >
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 opacity-50
                         bg-[repeating-linear-gradient(to_bottom,rgb(var(--accent)/0.05)_0_1px,transparent_1px_40px)]"
            />
            <div className="relative flex items-center justify-between gap-3">
              <span className="mono text-[10px] uppercase tracking-[0.2em] text-accent/90">After</span>
              <span className="mono text-[10px] uppercase tracking-[0.14em] text-faint">Aligned</span>
            </div>

            <h3 id={`${id}-after`} className="relative mt-4 text-lg font-bold tracking-tight text-text sm:text-xl">
              One privacy dashboard:
            </h3>

            <ul className="relative mt-7 flex flex-1 flex-col justify-center divide-y divide-accent/10">
              {AFTER.map((item, i) => (
                <motion.li
                  key={item.label}
                  className="flex items-center gap-3 py-3"
                  initial={reduced ? false : { opacity: 0, x: -14 }}
                  animate={show ? { opacity: 1, x: 0 } : undefined}
                  transition={
                    reduced
                      ? { duration: 0 }
                      : { duration: 0.5, delay: 0.35 + 0.09 * i, ease: [0.22, 1, 0.36, 1] }
                  }
                >
                  <span className="mono w-6 shrink-0 text-[10px] text-faint">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-accent/30 bg-accent/10 text-accent">
                    <item.Icon className="h-3.5 w-3.5" strokeWidth={2} aria-hidden="true" />
                  </span>
                  <span className="min-w-0 flex-1 truncate text-xs text-text sm:text-[13px]">
                    {item.label}
                  </span>
                  <Check className="h-3.5 w-3.5 shrink-0 text-accent" strokeWidth={2.5} aria-hidden="true" />
                </motion.li>
              ))}
            </ul>

            <p className="relative mt-6 text-[11px] leading-relaxed text-faint">
              One place to see it, one place to act, and a record of everything that was asked.
            </p>
          </section>
        </Reveal>
      </div>
    </Section>
  );
}

export default BeforeAfter;
