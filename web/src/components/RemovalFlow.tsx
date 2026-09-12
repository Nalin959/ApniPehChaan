import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  BrainCircuit, CircleCheckBig, FileText, Hourglass, Pause, Play, Radar, SendHorizontal,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { mockRemovalRequests } from "../data/mock";
import { useInViewOnce, usePrefersReducedMotion } from "../lib/hooks";
import { Pill, Reveal, Section } from "../lib/ui";
import type { RemovalRequest, RequestStage } from "../lib/types";

interface StageSpec {
  stage: RequestStage;
  label: string;
  caption: string;
  /** Short form shown in the request card's status line. */
  status: string;
  Icon: LucideIcon;
}

const STAGES: StageSpec[] = [
  { stage: "found",     label: "Found",             caption: "Listing located at the source", status: "Found",             Icon: Radar },
  { stage: "analysed",  label: "Analysed",          caption: "Exposed fields classified",     status: "Analysed",          Icon: BrainCircuit },
  { stage: "generated", label: "Request generated", caption: "Drafted for your approval",     status: "Request Generated", Icon: FileText },
  { stage: "sent",      label: "Request sent",      caption: "Delivered to the source",       status: "Request Sent",      Icon: SendHorizontal },
  { stage: "awaiting",  label: "Awaiting response", caption: "Tracked until they reply",      status: "Awaiting Response", Icon: Hourglass },
  { stage: "removed",   label: "Removed",           caption: "Verified, then monitored",      status: "Removed",           Icon: CircleCheckBig },
];

const STAGE_INDEX: Record<RequestStage, number> = STAGES.reduce(
  (acc, s, i) => { acc[s.stage] = i; return acc; },
  {} as Record<RequestStage, number>,
);

/** How long each step holds before advancing; the final step lingers so the loop reads as a resolution rather than a stutter. */
const STEP_MS = 1000;
const SETTLE_MS = 2800;

export interface RemovalFlowProps {
  id?: string;
  className?: string;
  /** Defaults to the mock layer; the first entry drives the demo card. */
  requests?: RemovalRequest[];
}

export function RemovalFlow({
  id = "removals",
  className = "",
  requests = mockRemovalRequests,
}: RemovalFlowProps) {
  const reduced = usePrefersReducedMotion();
  const { ref, seen } = useInViewOnce<HTMLDivElement>();
  const [active, setActive] = useState(0);
  const [playing, setPlaying] = useState(true);

  // One self-rescheduling timeout rather than an interval: the dwell time is
  // not uniform, and re-running the effect per step keeps cleanup trivial.
  useEffect(() => {
    if (reduced) {
      setActive(STAGES.length - 1);
      return;
    }
    if (!seen || !playing) return;
    const last = active === STAGES.length - 1;
    const t = window.setTimeout(
      () => setActive((a) => (a + 1) % STAGES.length),
      last ? SETTLE_MS : STEP_MS,
    );
    return () => window.clearTimeout(t);
  }, [seen, playing, active, reduced]);

  const demo = requests[0];
  const others = requests.slice(1);
  const current = STAGES[active];
  const progress = ((active + 1) / STAGES.length) * 100;

  return (
    <Section
      id={id}
      className={className}
      label="Removal pipeline"
      title={<>From exposure found <br className="hidden sm:block" />to record removed.</>}
      lead="Every listing follows the same path. You see exactly where each request is, who it went to and what is still outstanding — no black box, no guessing."
    >
      <div ref={ref} className="grid gap-8 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] lg:gap-10">
        {/* ---------------------------------------------------------------- */}
        {/* The pipeline                                                      */}
        {/* ---------------------------------------------------------------- */}
        <Reveal className="card p-5 sm:p-7">
          <div className="mb-7 flex flex-wrap items-center justify-between gap-3">
            <div className="label">Request lifecycle</div>
            <button
              type="button"
              onClick={() => setPlaying((p) => !p)}
              aria-pressed={!playing}
              className="btn-ghost px-3 py-1.5 text-[11px]"
            >
              {playing ? <Pause className="h-3 w-3" aria-hidden="true" /> : <Play className="h-3 w-3" aria-hidden="true" />}
              {playing ? "Pause" : "Play"}
              <span className="sr-only"> pipeline animation</span>
            </button>
          </div>

          <ol className="flex flex-col lg:flex-row lg:gap-5">
            {STAGES.map((s, i) => {
              const state = i < active ? "done" : i === active ? "active" : "pending";
              const filled = i < active;
              const hasNext = i < STAGES.length - 1;

              return (
                <li
                  key={s.stage}
                  aria-current={state === "active" ? "step" : undefined}
                  className="relative flex gap-4 pb-8 last:pb-0 lg:min-w-0 lg:flex-1 lg:flex-col lg:gap-0 lg:pb-0"
                >
                  {/* Rail: a vertical spine on mobile, a horizontal track on desktop. */}
                  <div className="relative flex w-6 shrink-0 self-stretch justify-center lg:h-7 lg:w-full lg:items-center lg:justify-start lg:self-auto">
                    {hasNext && (
                      <>
                        {/* mobile connector */}
                        <span aria-hidden="true" className="absolute left-1/2 top-[26px] bottom-[-30px] w-px -translate-x-1/2 bg-border lg:hidden" />
                        <motion.span
                          aria-hidden="true"
                          className="absolute left-1/2 top-[26px] bottom-[-30px] w-px -translate-x-1/2 origin-top bg-accent/60 lg:hidden"
                          animate={{ scaleY: filled ? 1 : 0 }}
                          initial={false}
                          transition={{ duration: reduced ? 0 : 0.45, ease: [0.22, 1, 0.36, 1] }}
                        />
                        {/* desktop connector */}
                        <span aria-hidden="true" className="absolute left-[26px] right-[-20px] top-[13px] hidden h-px bg-border lg:block" />
                        <motion.span
                          aria-hidden="true"
                          className="absolute left-[26px] right-[-20px] top-[13px] hidden h-px origin-left bg-accent/60 lg:block"
                          animate={{ scaleX: filled ? 1 : 0 }}
                          initial={false}
                          transition={{ duration: reduced ? 0 : 0.45, ease: [0.22, 1, 0.36, 1] }}
                        />
                      </>
                    )}

                    <span
                      className={`relative z-10 flex h-6 w-6 items-center justify-center rounded-full border transition-colors duration-300 ${
                        state === "pending"
                          ? "border-border bg-elevated text-faint"
                          : state === "done"
                            ? "border-accent/40 bg-accent/15 text-accent"
                            : "border-accent bg-accent text-[#04140c] shadow-glow-sm"
                      }`}
                    >
                      {state === "active" && !reduced && (
                        <span aria-hidden="true" className="absolute inset-0 animate-ping rounded-full bg-accent/25" />
                      )}
                      <s.Icon className="relative h-3 w-3" strokeWidth={2.25} aria-hidden="true" />
                    </span>
                  </div>

                  <div className="min-w-0 flex-1 lg:mt-3.5">
                    <div className="mono text-[10px] text-faint">{String(i + 1).padStart(2, "0")}</div>
                    <h3
                      className={`mt-1 text-[11px] font-bold uppercase tracking-[0.1em] transition-colors duration-300 ${
                        state === "pending" ? "text-faint" : "text-text"
                      }`}
                    >
                      {s.label}
                      <span className="sr-only">
                        {" — "}
                        {state === "done" ? "complete" : state === "active" ? "in progress" : "not started"}
                      </span>
                    </h3>
                    <p className="mt-1 text-xs leading-snug text-muted">{s.caption}</p>
                  </div>
                </li>
              );
            })}
          </ol>

          <div className="mt-8 flex items-center gap-4 border-t border-border pt-5">
            <div className="h-px flex-1 overflow-hidden bg-border">
              <motion.div
                className="h-px bg-accent"
                animate={{ width: `${progress}%` }}
                initial={false}
                transition={{ duration: reduced ? 0 : 0.5, ease: [0.22, 1, 0.36, 1] }}
              />
            </div>
            <span className="mono shrink-0 text-[10px] text-faint">
              {String(active + 1).padStart(2, "0")} / {String(STAGES.length).padStart(2, "0")}
            </span>
          </div>
        </Reveal>

        {/* ---------------------------------------------------------------- */}
        {/* The example request                                               */}
        {/* ---------------------------------------------------------------- */}
        <div className="flex flex-col gap-5">
          <Reveal delay={1} className="card overflow-hidden shadow-lift">
            <div className="flex items-center justify-between gap-3 border-b border-border bg-elevated/50 px-5 py-3.5">
              <span className="label text-accent">Privacy Request</span>
              <Pill className="border-border bg-bg/60 text-faint">{demo.id.replace("req-", "REQ-")}</Pill>
            </div>

            <dl className="divide-y divide-border px-5">
              <Field label="Source" value={demo.source} />
              <Field label="Request type" value={demo.type} />
              <Field
                label="Status"
                value={
                  reduced ? (
                    <span className="text-accent">{current.status}</span>
                  ) : (
                    <span className="relative inline-block">
                      <AnimatePresence mode="wait" initial={false}>
                        <motion.span
                          key={current.stage}
                          className="inline-block text-accent"
                          initial={{ opacity: 0, y: -8 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: 8 }}
                          transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                        >
                          {current.status}
                        </motion.span>
                      </AnimatePresence>
                    </span>
                  )
                }
              />
              <Field label="Submitted" value={demo.submitted} />
              {demo.deadlineDays !== undefined && (
                <Field label="Response window" value={`${demo.deadlineDays} days`} />
              )}
            </dl>

            <div className="border-t border-border px-5 py-3.5">
              <p className="text-[11px] leading-relaxed text-faint">
                Response times and obligations differ between organisations and jurisdictions.
                We track what was asked, when, and what came back.
              </p>
            </div>
          </Reveal>

          {others.length > 0 && (
            <Reveal delay={2} className="card p-5">
              <div className="label mb-4">Other open requests</div>
              <ul className="space-y-3">
                {others.map((r) => {
                  const spec = STAGES[STAGE_INDEX[r.stage]];
                  const done = r.stage === "removed";
                  return (
                    <li key={r.id} className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-xs font-semibold text-text">{r.source}</p>
                        <p className="mono truncate text-[10px] text-faint">{r.submitted}</p>
                      </div>
                      <Pill
                        className={
                          done
                            ? "shrink-0 border-accent/30 bg-accent/10 text-accent"
                            : "shrink-0 border-border-strong bg-elevated text-muted"
                        }
                      >
                        {spec.status}
                      </Pill>
                    </li>
                  );
                })}
              </ul>
            </Reveal>
          )}
        </div>
      </div>
    </Section>
  );
}

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-3.5">
      <dt className="label shrink-0">{label}</dt>
      <dd className="mono min-w-0 text-right text-xs text-text">{value}</dd>
    </div>
  );
}

export default RemovalFlow;
