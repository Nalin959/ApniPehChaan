import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity, BrainCircuit, Database, FileCheck, ListFilter, Radar, RadioTower,
  RefreshCw, Scale, SendHorizontal, ShieldCheck, TriangleAlert,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { ActivityFeed } from "./ActivityFeed";
import { mockRemovalRequests } from "../data/mock";
import { useInViewOnce, usePrefersReducedMotion } from "../lib/hooks";
import { Reveal, Section, StatusDot } from "../lib/ui";

interface Capability {
  id: string;
  label: string;
  caption: string;
  Icon: LucideIcon;
}

const CAPABILITIES: Capability[] = [
  { id: "scan",       label: "Scan",       caption: "Open web and brokers",   Icon: Radar },
  { id: "analyse",    label: "Analyse",    caption: "What is exposed",        Icon: BrainCircuit },
  { id: "prioritise", label: "Prioritise", caption: "By real-world risk",     Icon: ListFilter },
  { id: "request",    label: "Request",    caption: "Draft, then send",       Icon: SendHorizontal },
  { id: "follow-up",  label: "Follow up",  caption: "Chase the reply",        Icon: RefreshCw },
  { id: "monitor",    label: "Monitor",    caption: "Watch for reappearance", Icon: RadioTower },
];

interface Point { x: number; y: number }

/**
 * Layout is expressed as percentages, and the connector SVG uses a 0-100
 * viewBox with preserveAspectRatio="none" — so SVG units and CSS percentages
 * are the same coordinate space and the lines land on the HTML nodes exactly.
 * `vector-effect="non-scaling-stroke"` keeps strokes and dashes even despite
 * the non-uniform scale.
 */
const RADIAL_CENTRE: Point = { x: 50, y: 50 };
const RADIAL_NODES: Point[] = [
  { x: 50,   y: 17 },   // scan          — 12 o'clock, clockwise from here
  { x: 78.6, y: 33.5 }, // analyse
  { x: 78.6, y: 66.5 }, // prioritise
  { x: 50,   y: 83 },   // request
  { x: 21.4, y: 66.5 }, // follow up
  { x: 21.4, y: 33.5 }, // monitor
];

const COLUMN_CENTRE: Point = { x: 46, y: 8.5 };
const COLUMN_NODES: Point[] = [22, 35.4, 48.8, 62.2, 75.6, 89].map((y) => ({ x: 46, y }));

/** Below this container width the radial diagram stops being readable and becomes a spine. */
const RADIAL_MIN_WIDTH = 520;

const INPUTS: { label: string; Icon: LucideIcon }[] = [
  { label: "Data brokers",   Icon: Database },
  { label: "Breach records", Icon: TriangleAlert },
  { label: "Public records", Icon: Scale },
];

const OUTPUTS: { label: string; Icon: LucideIcon }[] = [
  { label: "Removal requests",     Icon: FileCheck },
  { label: "Continuous monitoring", Icon: Activity },
];

export interface PrivacyAgentProps {
  id?: string;
  className?: string;
  /** Height of the embedded activity feed body, in pixels. */
  feedHeight?: number;
}

export function PrivacyAgent({
  id = "privacy-agent",
  className = "",
  feedHeight = 340,
}: PrivacyAgentProps) {
  const reduced = usePrefersReducedMotion();
  const { ref: sectionRef, seen } = useInViewOnce<HTMLDivElement>();
  const boxRef = useRef<HTMLDivElement | null>(null);

  // Column is the safe default: it is readable at every width, so a first paint
  // before measurement can never show a broken radial on a phone.
  const [mode, setMode] = useState<"radial" | "column">("column");
  const [active, setActive] = useState(0);

  useEffect(() => {
    const el = boxRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 0;
      setMode(w >= RADIAL_MIN_WIDTH ? "radial" : "column");
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // The travelling highlight is what makes the agent read as running rather
  // than drawn. It only runs once the diagram is on screen.
  useEffect(() => {
    if (reduced || !seen) return;
    const t = window.setInterval(
      () => setActive((a) => (a + 1) % CAPABILITIES.length),
      1500,
    );
    return () => window.clearInterval(t);
  }, [reduced, seen]);

  const radial = mode === "radial";
  const centre = radial ? RADIAL_CENTRE : COLUMN_CENTRE;
  const nodes = radial ? RADIAL_NODES : COLUMN_NODES;

  // Radial: six spokes out of the core. Column: a chain, so the lines do not
  // stack on top of each other when every node shares an x.
  const segments: [Point, Point][] = radial
    ? nodes.map((n) => [centre, n] as [Point, Point])
    : nodes.map((n, i) => [i === 0 ? centre : nodes[i - 1], n] as [Point, Point]);

  const openRequests = mockRemovalRequests.filter((r) => r.stage !== "removed").length;
  const closedRequests = mockRemovalRequests.length - openRequests;

  return (
    <Section
      id={id}
      className={className}
      label="Privacy agent"
      title="Meet your personal privacy agent."
      lead="Instead of checking your digital footprint manually, let an intelligent agent continuously watch for exposure and help you take action."
    >
      <div ref={sectionRef} className="grid gap-6 lg:grid-cols-[minmax(0,1.32fr)_minmax(0,1fr)] lg:gap-8">
        {/* ----------------------------------------------------------------- */}
        {/* The agent diagram                                                  */}
        {/* ----------------------------------------------------------------- */}
        <Reveal className="card relative overflow-hidden p-5 shadow-lift sm:p-7">
          <div aria-hidden="true" className="pointer-events-none absolute inset-0 grid-bg opacity-[0.35] mask-fade-b" />

          <div className="relative">
            <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
              <div className="label">Agent loop</div>
              <div className="flex items-center gap-2">
                <StatusDot tone="accent" live={!reduced} />
                <span className="mono text-[10px] uppercase tracking-[0.14em] text-faint">
                  Running continuously
                </span>
              </div>
            </div>

            <FlowBand title="Sources in" items={INPUTS} placement="above" reduced={reduced} />

            <div
              ref={boxRef}
              className={`relative mx-auto w-full ${radial ? "h-[500px] max-w-[720px]" : "h-[680px]"}`}
            >
              <svg
                aria-hidden="true"
                className="absolute inset-0 h-full w-full"
                viewBox="0 0 100 100"
                preserveAspectRatio="none"
              >
                {/* The closed loop: an ellipse through the six nodes on desktop,
                    a return curve from the last node on mobile. Either way the
                    message is that the cycle does not end. */}
                <g className="text-accent" fill="none" strokeWidth={1} vectorEffect="non-scaling-stroke">
                  {radial ? (
                    <ellipse
                      cx={RADIAL_CENTRE.x} cy={RADIAL_CENTRE.y} rx={33} ry={33}
                      stroke="currentColor" strokeOpacity={0.18}
                      strokeDasharray="4 8" vectorEffect="non-scaling-stroke"
                      className={reduced ? undefined : "animate-dash-flow"}
                    />
                  ) : (
                    <path
                      d={`M ${COLUMN_NODES[5].x} ${COLUMN_NODES[5].y} C 92 ${COLUMN_NODES[5].y}, 92 ${COLUMN_CENTRE.y}, ${COLUMN_CENTRE.x} ${COLUMN_CENTRE.y}`}
                      stroke="currentColor" strokeOpacity={0.2}
                      strokeDasharray="4 8" vectorEffect="non-scaling-stroke"
                      className={reduced ? undefined : "animate-dash-flow"}
                    />
                  )}
                </g>

                {segments.map(([a, b], i) => (
                  <g key={CAPABILITIES[i].id} vectorEffect="non-scaling-stroke">
                    <line
                      x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                      className="text-border-strong" stroke="currentColor"
                      strokeWidth={1} vectorEffect="non-scaling-stroke"
                    />
                    <line
                      x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                      className={`text-accent ${reduced ? "" : "animate-dash-flow"}`}
                      stroke="currentColor"
                      strokeOpacity={!reduced && active === i ? 0.9 : 0.32}
                      strokeWidth={!reduced && active === i ? 1.6 : 1}
                      strokeDasharray="4 8"
                      vectorEffect="non-scaling-stroke"
                    />
                  </g>
                ))}
              </svg>

              {/* Core */}
              <div
                className="absolute -translate-x-1/2 -translate-y-1/2"
                style={{ left: `${centre.x}%`, top: `${centre.y}%` }}
              >
                <AgentCore reduced={reduced} size={radial ? 132 : 104} />
              </div>

              {/* Capability nodes. Real text in DOM order — the SVG above is
                  decorative and carries no information of its own. */}
              <ul className="absolute inset-0">
                {CAPABILITIES.map((c, i) => {
                  const p = nodes[i];
                  const isActive = !reduced && active === i;
                  return (
                    <li
                      key={c.id}
                      className="absolute -translate-x-1/2 -translate-y-1/2"
                      style={{ left: `${p.x}%`, top: `${p.y}%` }}
                    >
                      <motion.div
                        initial={reduced ? false : { opacity: 0, scale: 0.9 }}
                        animate={seen || reduced ? { opacity: 1, scale: 1 } : undefined}
                        transition={{ duration: 0.45, delay: reduced ? 0 : 0.12 * i, ease: [0.22, 1, 0.36, 1] }}
                        className={`flex items-center rounded-card border bg-surface/90 backdrop-blur-[2px]
                                    transition-colors duration-300 ${
                          radial
                            ? "w-[118px] flex-col gap-1.5 px-2.5 py-3 text-center"
                            : "w-[196px] gap-3 px-3 py-2.5 text-left"
                        } ${
                          isActive
                            ? "border-accent/60 bg-elevated shadow-glow-sm"
                            : "border-border"
                        }`}
                      >
                        <span
                          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border transition-colors duration-300 ${
                            isActive
                              ? "border-accent/50 bg-accent/15 text-accent"
                              : "border-border bg-elevated text-muted"
                          }`}
                        >
                          <c.Icon className="h-3.5 w-3.5" strokeWidth={2} aria-hidden="true" />
                        </span>
                        <span className={radial ? "block" : "min-w-0"}>
                          <span
                            className={`mono block text-[10px] font-semibold uppercase tracking-[0.14em] transition-colors duration-300 ${
                              isActive ? "text-accent" : "text-text"
                            }`}
                          >
                            {c.label}
                          </span>
                          <span className="mt-0.5 block text-[10px] leading-snug text-faint">
                            {c.caption}
                          </span>
                        </span>
                      </motion.div>
                    </li>
                  );
                })}
              </ul>
            </div>

            <FlowBand title="Actions out" items={OUTPUTS} placement="below" reduced={reduced} />
          </div>
        </Reveal>

        {/* ----------------------------------------------------------------- */}
        {/* Live feed + a short ledger, so the diagram has evidence beside it   */}
        {/* ----------------------------------------------------------------- */}
        <div className="flex flex-col gap-5 lg:sticky lg:top-24 lg:self-start">
          <Reveal delay={1}>
            <ActivityFeed height={feedHeight} />
          </Reveal>

          <Reveal delay={2} className="card p-5">
            <div className="label mb-4">Agent ledger</div>
            <dl className="grid grid-cols-2 gap-4">
              <Stat label="Open requests" value={openRequests} tone="text-text" />
              <Stat label="Confirmed removed" value={closedRequests} tone="text-accent" />
            </dl>
            <p className="mt-4 border-t border-border pt-4 text-[11px] leading-relaxed text-faint">
              The agent proposes; you approve. Nothing is sent on your behalf until you say so.
            </p>
          </Reveal>
        </div>
      </div>
    </Section>
  );
}

/** Core of the diagram: breathing, with expanding rings, so it reads as live. */
function AgentCore({ reduced, size }: { reduced: boolean; size: number }) {
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      {!reduced &&
        [0, 1].map((i) => (
          <motion.span
            key={i}
            aria-hidden="true"
            className="absolute inset-0 rounded-full border border-accent/40"
            initial={{ scale: 1, opacity: 0.5 }}
            animate={{ scale: 1.85, opacity: 0 }}
            transition={{ duration: 2.8, repeat: Infinity, delay: i * 1.4, ease: "easeOut" }}
          />
        ))}

      <motion.div
        className="relative grid h-full w-full place-items-center rounded-full border border-accent/45
                   bg-[radial-gradient(circle_at_50%_35%,rgb(var(--accent)/0.18),rgb(var(--surface))_70%)]
                   shadow-glow"
        animate={reduced ? undefined : { scale: [1, 1.035, 1] }}
        transition={{ duration: 3.6, repeat: Infinity, ease: "easeInOut" }}
      >
        <div className="text-center">
          <ShieldCheck className="mx-auto h-5 w-5 text-accent" strokeWidth={1.75} aria-hidden="true" />
          <p className="mono mt-1.5 text-[10px] font-bold uppercase tracking-[0.2em] text-text">
            Agent
          </p>
          <p className="mono mt-0.5 text-[9px] uppercase tracking-[0.16em] text-accent/80">
            Active
          </p>
        </div>
      </motion.div>
    </div>
  );
}

/** A labelled row of source/action chips, tied to the diagram by a dashed feed line. */
function FlowBand({
  title, items, placement, reduced,
}: {
  title: string;
  items: { label: string; Icon: LucideIcon }[];
  placement: "above" | "below";
  reduced: boolean;
}) {
  return (
    <div className={placement === "above" ? "mb-1" : "mt-1"}>
      <p className="label mb-3 text-center">{title}</p>
      <ul className="flex flex-wrap items-start justify-center gap-x-4 gap-y-3 sm:gap-x-8">
        {items.map((item) => (
          <li key={item.label} className="flex flex-col items-center">
            {placement === "below" && <FeedLine reduced={reduced} />}
            <span className="inline-flex items-center gap-2 rounded-pill border border-border bg-elevated/70 px-3 py-1.5">
              <item.Icon className="h-3 w-3 shrink-0 text-muted" strokeWidth={2} aria-hidden="true" />
              <span className="mono text-[10px] uppercase tracking-[0.12em] text-muted">
                {item.label}
              </span>
            </span>
            {placement === "above" && <FeedLine reduced={reduced} />}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Decorative dashed feed line with an arrowhead, always pointing downstream. */
function FeedLine({ reduced }: { reduced: boolean }) {
  return (
    <svg aria-hidden="true" width="10" height="26" viewBox="0 0 10 26" className="text-accent/50">
      <line
        x1="5" y1="0" x2="5" y2="19"
        stroke="currentColor" strokeWidth="1" strokeDasharray="4 8"
        className={reduced ? undefined : "animate-dash-flow"}
      />
      <path d="M5 25 L1.6 18.5 H8.4 Z" fill="currentColor" />
    </svg>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div>
      <dt className="label">{label}</dt>
      <dd className={`mono mt-1.5 text-2xl font-bold ${tone}`}>
        {String(value).padStart(2, "0")}
      </dd>
    </div>
  );
}

export default PrivacyAgent;
