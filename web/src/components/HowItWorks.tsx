/**
 * HowItWorks — four steps, four different machines.
 *
 * Each step gets a visual that behaves the way the step behaves: the scan
 * sweeps, the classifier resolves into verdicts, the request walks a pipeline,
 * the monitor never stops. Four copies of the same icon-in-a-circle would say
 * nothing about what the product actually does.
 *
 * Every visual arms on `useInViewOnce`, so the card animates when the reader
 * arrives at it rather than burning its one moment off-screen.
 */
import { useEffect, useState } from "react";
import type { ComponentType } from "react";
import { motion } from "framer-motion";
import { Activity, Radar, Scale, Send } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useInViewOnce, usePrefersReducedMotion } from "../lib/hooks";
import { Reveal, Section } from "../lib/ui";

export interface HowItWorksProps {
  /** Anchor id — defaults to the value the page nav links to. */
  id?: string;
  className?: string;
}

interface StepVisualProps {
  /** True once the card has been scrolled into view. */
  active: boolean;
  reduced: boolean;
}

const PANEL =
  "relative h-28 overflow-hidden rounded-lg border border-border bg-bg/70 p-3.5";

/** 01 SCAN — a sweep passing over candidate sources, lighting them as it goes. */
function ScanVisual({ active, reduced }: StepVisualProps) {
  const rows = [72, 46, 88, 58];
  return (
    <div className={PANEL} aria-hidden="true">
      <div className="flex h-full flex-col justify-center gap-3">
        {rows.map((w, i) => (
          <div key={w} className="flex items-center gap-2">
            <span
              className={`h-1.5 w-1.5 shrink-0 rounded-full transition-colors duration-500
                          ${active ? "bg-accent" : "bg-border-strong"}`}
              style={reduced ? undefined : { transitionDelay: `${i * 260}ms` }}
            />
            <span
              className="h-1 rounded-full bg-border-strong/60 transition-all duration-700"
              style={{
                width: active ? `${w}%` : "12%",
                transitionDelay: reduced ? undefined : `${i * 120}ms`,
              }}
            />
          </div>
        ))}
      </div>
      {active && !reduced && (
        <div className="pointer-events-none absolute inset-x-0 top-0 h-10 animate-scan-sweep
                        bg-gradient-to-b from-transparent via-accent/10 to-transparent">
          <div className="absolute bottom-0 h-px w-full bg-accent/80 shadow-glow-sm" />
        </div>
      )}
    </div>
  );
}

/** 02 UNDERSTAND — raw findings resolving into graded verdicts. */
function ClassifyVisual({ active, reduced }: StepVisualProps) {
  const rows = [
    { field: "EMAIL", width: 82, bar: "bg-danger", tag: "HIGH", text: "text-danger" },
    { field: "PHONE", width: 58, bar: "bg-warning", tag: "MED", text: "text-warning" },
    { field: "PROFILE", width: 31, bar: "bg-accent", tag: "LOW", text: "text-accent" },
  ];
  return (
    <div className={PANEL} aria-hidden="true">
      <div className="flex h-full flex-col justify-center gap-3">
        {rows.map((row, i) => (
          <div key={row.field} className="flex items-center gap-2">
            <span className="mono w-14 shrink-0 text-[9px] tracking-[0.12em] text-faint">
              {row.field}
            </span>
            <span className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-border-strong/30">
              <span
                className={`block h-full rounded-full transition-all duration-700 ease-out ${row.bar}`}
                style={{
                  width: active ? `${row.width}%` : "0%",
                  transitionDelay: reduced ? undefined : `${i * 220}ms`,
                }}
              />
            </span>
            <span
              className={`mono w-8 shrink-0 text-right text-[9px] tracking-[0.1em]
                          transition-opacity duration-500 ${row.text}
                          ${active ? "opacity-100" : "opacity-0"}`}
              style={reduced ? undefined : { transitionDelay: `${i * 220 + 420}ms` }}
            >
              {row.tag}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

const STAGES = ["DRAFT", "SENT", "AWAIT", "GONE"] as const;

/** 03 REMOVE — one request walking the pipeline, stage by stage. */
function RequestVisual({ active, reduced }: StepVisualProps) {
  const [stage, setStage] = useState(0);

  useEffect(() => {
    if (!active) return;
    if (reduced) {
      setStage(STAGES.length - 1);
      return;
    }
    let i = 0;
    const timer = window.setInterval(() => {
      i += 1;
      setStage(i);
      if (i >= STAGES.length - 1) window.clearInterval(timer);
    }, 850);
    return () => window.clearInterval(timer);
  }, [active, reduced]);

  return (
    <div className={PANEL} aria-hidden="true">
      <div className="flex h-full flex-col justify-center gap-4">
        <div className="flex items-center">
          {STAGES.map((label, i) => {
            const reached = active && i <= stage;
            return (
              <div key={label} className="flex min-w-0 flex-1 items-center last:flex-none">
                <span className="relative flex h-3 w-3 shrink-0 items-center justify-center">
                  <span
                    className={`h-3 w-3 rounded-full border transition-all duration-300
                                ${reached
                                  ? "border-accent bg-accent/25"
                                  : "border-border-strong bg-elevated"}`}
                  />
                  {reached && (
                    <span className="absolute h-1.5 w-1.5 rounded-full bg-accent" />
                  )}
                </span>
                {i < STAGES.length - 1 && (
                  <span className="mx-1 h-px min-w-0 flex-1 bg-border-strong/50">
                    <span
                      className="block h-px bg-accent/70 transition-all duration-500 ease-out"
                      style={{ width: active && i < stage ? "100%" : "0%" }}
                    />
                  </span>
                )}
              </div>
            );
          })}
        </div>
        <div className="flex items-center justify-between gap-2">
          {STAGES.map((label, i) => (
            <span
              key={label}
              className={`mono text-[9px] tracking-[0.1em] transition-colors duration-300
                          ${active && i <= stage ? "text-text" : "text-faint"}`}
            >
              {label}
            </span>
          ))}
        </div>
        <div className="mono text-[9px] tracking-[0.12em] text-faint">
          STATUS::{active ? STAGES[Math.min(stage, STAGES.length - 1)] : "IDLE"}
        </div>
      </div>
    </div>
  );
}

/** 04 MONITOR — a pulse that repeats forever, because the watch never ends. */
function MonitorVisual({ active, reduced }: StepVisualProps) {
  const live = active && !reduced;
  return (
    <div className={`${PANEL} flex items-center gap-3`} aria-hidden="true">
      <svg
        viewBox="0 0 120 120"
        preserveAspectRatio="xMidYMid meet"
        className="h-full w-auto shrink-0"
        focusable="false"
      >
        {/* Expanding rings need a scale keyframe the shared config does not carry,
            so this one visual drives it from framer-motion instead. */}
        {[0, 1, 2].map((i) => (
          <motion.circle
            key={i}
            cx={60}
            cy={60}
            r={50}
            fill="none"
            strokeWidth={1.5}
            className="stroke-accent"
            style={{ transformOrigin: "60px 60px" }}
            initial={{ scale: 0.28, opacity: 0.45 }}
            animate={
              live
                ? { scale: [0.28, 1], opacity: [0.45, 0] }
                : { scale: 0.32 + i * 0.3, opacity: 0.3 - i * 0.08 }
            }
            transition={
              live
                ? { duration: 2.4, delay: i * 0.8, repeat: Infinity, ease: "easeOut" }
                : { duration: 0 }
            }
          />
        ))}
        <circle cx={60} cy={60} r={14} className="fill-accent/10 stroke-accent/40" strokeWidth={1} />
        <circle cx={60} cy={60} r={4} className="fill-accent" />
      </svg>

      <div className="flex min-w-0 flex-col gap-1.5">
        <span className="mono text-[9px] tracking-[0.12em] text-faint">WATCH::ACTIVE</span>
        <span className="mono truncate text-[11px] text-text">no new exposure</span>
        <span className="mono flex items-center gap-1 text-[9px] tracking-[0.12em] text-accent">
          next sweep 04:00
          {live && <span className="animate-blink">_</span>}
        </span>
      </div>
    </div>
  );
}

interface Step {
  n: string;
  title: string;
  copy: string;
  Icon: LucideIcon;
  Visual: ComponentType<StepVisualProps>;
}

const STEPS: Step[] = [
  {
    n: "01",
    title: "Scan",
    copy: "Search the internet and known data sources for traces of your personal information.",
    Icon: Radar,
    Visual: ScanVisual,
  },
  {
    n: "02",
    title: "Understand",
    copy: "Identify exactly what information is exposed and how serious each finding is.",
    Icon: Scale,
    Visual: ClassifyVisual,
  },
  {
    n: "03",
    title: "Remove",
    copy: "Generate appropriate privacy requests and track the removal process.",
    Icon: Send,
    Visual: RequestVisual,
  },
  {
    n: "04",
    title: "Monitor",
    copy: "Continuously check for new exposure and reappearance.",
    Icon: Activity,
    Visual: MonitorVisual,
  },
];

function StepCard({ step, reduced }: { step: Step; reduced: boolean }) {
  const { ref, seen } = useInViewOnce<HTMLLIElement>();
  const { Icon, Visual } = step;
  const active = seen || reduced;

  return (
    <li ref={ref} className="card card-hover flex flex-col gap-5 p-5">
      <div className="flex items-center justify-between gap-3">
        <span className="mono text-sm font-bold text-faint">{step.n}</span>
        <Icon className="h-4 w-4 text-accent" aria-hidden="true" strokeWidth={1.75} />
      </div>

      <Visual active={active} reduced={reduced} />

      <div>
        <h3 className="mono text-xs uppercase tracking-[0.18em] text-text">{step.title}</h3>
        <p className="mt-2.5 text-sm leading-relaxed text-muted">{step.copy}</p>
      </div>
    </li>
  );
}

export function HowItWorks({ id = "how-it-works", className = "" }: HowItWorksProps) {
  const reduced = usePrefersReducedMotion();

  return (
    <Section
      id={id}
      className={className}
      label="How it works"
      title="Four steps, running continuously."
      lead="Finding the exposure is the easy half. The product earns its keep in what happens
            after — classifying it, acting on it, and noticing when it comes back."
    >
      <Reveal>
        <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step) => (
            <StepCard key={step.n} step={step} reduced={reduced} />
          ))}
        </ol>
      </Reveal>
    </Section>
  );
}

export default HowItWorks;
