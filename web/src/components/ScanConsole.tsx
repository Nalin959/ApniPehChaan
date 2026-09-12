import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { usePrefersReducedMotion } from "../lib/hooks";
import { scanSteps } from "../data/mock";
import type { ScanResult } from "../lib/types";

export type ScanConsoleState = "idle" | "running" | "complete";

export interface ScanConsoleProps {
  state: ScanConsoleState;
  result: ScanResult | null;
  /** Fires once the last step resolves. The parent owns the state machine. */
  onDone?: () => void;
}

/** Counts read as instrument output, not prose — always two digits. */
function pad2(n: number) {
  return String(n).padStart(2, "0");
}

const TOTAL_STEPS = scanSteps.length;

export default function ScanConsole({ state, result, onDone }: ScanConsoleProps) {
  const reduced = usePrefersReducedMotion();
  /** Steps resolved so far *in the current run*. Only meaningful while running. */
  const [tick, setTick] = useState(0);
  const [prevState, setPrevState] = useState(state);

  // Resetting during render rather than in an effect: a fresh run must start at
  // zero in the same commit it becomes visible, or the panel flashes the
  // previous run's progress for a frame.
  if (prevState !== state) {
    setPrevState(state);
    if (state === "running") setTick(0);
  }

  // Held in a ref so a new callback identity from the parent cannot restart the
  // timer chain mid-scan.
  const onDoneRef = useRef(onDone);
  useEffect(() => {
    onDoneRef.current = onDone;
  }, [onDone]);

  useEffect(() => {
    if (state !== "running") return;

    // With reduced motion the staged reveal carries no information the end
    // state does not, so it is skipped entirely.
    if (reduced) {
      onDoneRef.current?.();
      return;
    }

    let index = 0;
    let timer = 0;

    // Self-rescheduling rather than a fixed interval, because each step
    // declares its own duration.
    const schedule = () => {
      timer = window.setTimeout(() => {
        index += 1;
        setTick(index);
        if (index < TOTAL_STEPS) schedule();
        else onDoneRef.current?.();
      }, scanSteps[index].duration);
    };
    schedule();

    // Only one timer is ever outstanding, so clearing the latest is enough to
    // guarantee no setState lands after unmount.
    return () => window.clearTimeout(timer);
  }, [state, reduced]);

  // Idle and complete are fully determined by the prop; only a live run needs
  // the ticking state. Reduced motion jumps straight to the finished list.
  const doneCount =
    state === "complete" ? TOTAL_STEPS
    : state === "running" ? (reduced ? TOTAL_STEPS : tick)
    : 0;

  const counts = result?.counts ?? { total: 0, high: 0, medium: 0, low: 0 };
  const activeStep = state === "running" && doneCount < TOTAL_STEPS ? scanSteps[doneCount] : null;

  const statusText =
    state === "complete"
      ? `Scan complete. ${counts.total} sources found: ${counts.high} high risk, ${counts.medium} medium risk, ${counts.low} low risk.`
      : state === "running"
        ? `Scanning. ${doneCount} of ${TOTAL_STEPS} checks complete.`
        : "Scanner idle. Awaiting an email address.";

  return (
    <div className="card relative overflow-hidden shadow-lift">
      {/* Faux chrome: signals "tool", not "marketing panel". */}
      <div className="flex items-center gap-3 border-b border-border bg-elevated/60 px-4 py-3">
        <span className="flex items-center gap-1.5" aria-hidden>
          <span className="h-2 w-2 rounded-full bg-border-strong" />
          <span className="h-2 w-2 rounded-full bg-border-strong" />
          <span className="h-2 w-2 rounded-full bg-border-strong" />
        </span>
        <span className="label truncate text-faint">DIGITAL FOOTPRINT SCAN</span>
        <span className="ml-auto flex items-center gap-2">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              state === "running"
                ? "animate-pulse-dot bg-accent"
                : state === "complete"
                  ? "bg-accent"
                  : "bg-faint"
            }`}
            aria-hidden
          />
          <span className="label text-faint">
            {state === "running" ? "LIVE" : state === "complete" ? "DONE" : "IDLE"}
          </span>
        </span>
      </div>

      <div className="relative min-h-[334px] px-4 py-5 sm:px-5">
        {/* Decorative sweep. Sits under the content so text never dims. */}
        {state === "running" && !reduced && (
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 top-0 z-0 h-24 animate-scan-sweep
                       bg-gradient-to-b from-transparent via-accent/[0.07] to-transparent"
          />
        )}

        <div className="relative z-10">
          <AnimatePresence mode="wait" initial={false}>
            {state === "complete" ? (
              <motion.div
                key="complete"
                initial={reduced ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
                className="flex min-h-[294px] flex-col justify-center"
              >
                <div className="label mb-3 text-accent">SCAN COMPLETE</div>

                <div className="flex items-baseline gap-3">
                  <span className="mono text-[clamp(2.5rem,9vw,3.75rem)] font-bold leading-none tracking-tight text-text">
                    {pad2(counts.total)}
                  </span>
                  <span className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">
                    Sources
                    <br />
                    Found
                  </span>
                </div>

                <div className="mt-6 flex flex-wrap items-center gap-x-2 gap-y-2 font-mono text-[10px] tracking-[0.12em] sm:text-[11px]">
                  <span className="text-danger">{pad2(counts.high)} HIGH RISK</span>
                  <span className="text-faint" aria-hidden>/</span>
                  <span className="text-warning">{pad2(counts.medium)} MEDIUM RISK</span>
                  <span className="text-faint" aria-hidden>/</span>
                  <span className="text-accent">{pad2(counts.low)} LOW RISK</span>
                </div>

                {/* Proportional bar — the split is easier to feel than to read. */}
                <div className="mt-5 flex h-1.5 w-full overflow-hidden rounded-pill bg-elevated" aria-hidden>
                  <span className="bg-danger" style={{ width: `${(counts.high / Math.max(counts.total, 1)) * 100}%` }} />
                  <span className="bg-warning" style={{ width: `${(counts.medium / Math.max(counts.total, 1)) * 100}%` }} />
                  <span className="bg-accent" style={{ width: `${(counts.low / Math.max(counts.total, 1)) * 100}%` }} />
                </div>

                {result?.email && (
                  <p className="mt-5 break-all font-mono text-[11px] text-faint">
                    <span className="text-accent">&gt;</span> {result.email}
                  </p>
                )}
              </motion.div>
            ) : (
              <motion.div
                key="steps"
                initial={false}
                exit={reduced ? { opacity: 0 } : { opacity: 0, y: -8 }}
                transition={{ duration: 0.25 }}
              >
                <p className="mb-4 font-mono text-[11px] text-faint">
                  <span className="text-accent">&gt;</span>{" "}
                  {state === "running" ? "running footprint scan" : "awaiting target address"}
                  <span className="ml-0.5 inline-block animate-blink text-accent" aria-hidden>
                    ▊
                  </span>
                </p>

                <ul className="space-y-px">
                  {scanSteps.map((step, i) => {
                    const done = i < doneCount;
                    const active = state === "running" && i === doneCount;
                    return (
                      <li
                        key={step.id}
                        className={`flex items-center gap-3 rounded-md px-2 py-2.5 transition-colors duration-300 ${
                          active ? "bg-accent/[0.06]" : ""
                        }`}
                      >
                        <span
                          aria-hidden
                          className={`w-4 shrink-0 text-center font-mono text-xs ${
                            done ? "text-accent" : active ? "text-accent" : "text-faint/60"
                          }`}
                        >
                          {done ? "✓" : active ? <span className="inline-block animate-spin">◌</span> : "·"}
                        </span>

                        <span
                          className={`flex-1 truncate text-[13px] transition-colors duration-300 ${
                            done ? "text-text" : active ? "text-text" : "text-faint"
                          }`}
                        >
                          {step.label}
                        </span>

                        <span
                          className={`shrink-0 font-mono text-[9px] tracking-[0.16em] ${
                            done ? "text-accent" : active ? "text-muted" : "text-faint/60"
                          }`}
                        >
                          {done ? "CHECKED" : active ? "SCANNING" : "WAITING"}
                        </span>
                      </li>
                    );
                  })}
                </ul>

                <div className="mt-5 border-t border-border pt-4">
                  <div className="flex items-center justify-between font-mono text-[10px] tracking-[0.14em] text-faint">
                    <span>{state === "running" ? (activeStep?.label ?? "FINALISING").toUpperCase() : "READY"}</span>
                    <span>
                      {pad2(doneCount)}/{pad2(TOTAL_STEPS)}
                    </span>
                  </div>
                  <div className="mt-2 h-px w-full bg-border">
                    <div
                      className="h-px bg-accent transition-[width] duration-500 ease-out"
                      style={{ width: `${(doneCount / TOTAL_STEPS) * 100}%` }}
                    />
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* The scan is asynchronous, so its outcome is announced rather than only shown. */}
      <p className="sr-only" role="status" aria-live="polite">
        {statusText}
      </p>
    </div>
  );
}
