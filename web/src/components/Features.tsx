import type { CSSProperties, ReactNode } from "react";
import {
  Activity, Clock, Database, ListFilter, Radar, ScanSearch, Send, ShieldAlert,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Reveal, Section } from "../lib/ui";
import { usePrefersReducedMotion } from "../lib/hooks";

/** Features takes no props — the grid is fixed content. */
export interface FeaturesProps {
  className?: string;
}

/* ------------------------------------------------------- hover micro-visuals */

/** Staggered delays are dropped under reduced motion so nothing lags visibly. */
function useStagger() {
  const reduced = usePrefersReducedMotion();
  return (index: number, step = 70) => ({ transitionDelay: reduced ? "0ms" : `${index * step}ms` });
}

/** Data Broker Discovery — cells light up left to right as the sweep finds them. */
function BrokerCells() {
  const stagger = useStagger();
  return (
    <div className="flex gap-1" aria-hidden="true">
      {Array.from({ length: 7 }, (_, i) => (
        <span
          key={i}
          style={stagger(i, 55)}
          className="h-5 w-3 rounded-[3px] border border-border bg-elevated transition-colors duration-300
                     group-hover:border-accent/40 group-hover:bg-accent/25"
        />
      ))}
    </div>
  );
}

/** Breach Monitoring — a flat baseline that spikes, with one bar going red. */
function BreachSpark() {
  const stagger = useStagger();
  const heights = [30, 45, 25, 60, 38, 100, 42, 55, 30, 48];
  return (
    <div className="flex h-6 items-end gap-[3px]" aria-hidden="true">
      {heights.map((h, i) => (
        <span
          key={i}
          style={{ ...stagger(i, 40), "--h": `${h}%` } as CSSProperties}
          className={`h-[2px] w-[3px] rounded-pill transition-[height] duration-300 group-hover:h-[var(--h)] ${
            h === 100 ? "bg-danger" : "bg-border-strong group-hover:bg-muted"
          }`}
        />
      ))}
    </div>
  );
}

/** Risk Prioritisation — three bars that extend to their real weights. */
function RiskBars() {
  const stagger = useStagger();
  const rows = [
    { tone: "bg-danger", width: "92%" },
    { tone: "bg-warning", width: "58%" },
    { tone: "bg-accent", width: "26%" },
  ];
  return (
    <div className="w-full space-y-1.5" aria-hidden="true">
      {rows.map((r, i) => (
        <span key={r.tone} className="block h-1 w-full overflow-hidden rounded-pill bg-elevated">
          <span
            style={{ ...stagger(i, 80), "--w": r.width } as CSSProperties}
            className={`block h-full w-[8%] ${r.tone} transition-[width] duration-500 ease-out group-hover:w-[var(--w)]`}
          />
        </span>
      ))}
    </div>
  );
}

/** Removal Tracking — the track fills and the tick lands. */
function RemovalTrack() {
  return (
    <div className="flex w-full items-center gap-2" aria-hidden="true">
      <span className="h-1 flex-1 overflow-hidden rounded-pill bg-elevated">
        <span className="block h-full w-[18%] bg-accent transition-[width] duration-700 ease-out group-hover:w-full" />
      </span>
      <span className="mono text-[10px] text-faint transition-colors duration-300 group-hover:text-accent">
        done
      </span>
    </div>
  );
}

/** Continuous Monitoring — rings push outward from a live centre dot. */
function MonitorRings() {
  const stagger = useStagger();
  return (
    <div className="relative h-6 w-full" aria-hidden="true">
      <span className="absolute left-3 top-1/2 h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent animate-pulse-dot" />
      {[10, 18, 26].map((size, i) => (
        <span
          key={size}
          style={{ ...stagger(i, 90), width: size, height: size }}
          className="absolute left-3 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-accent/25
                     opacity-0 transition-all duration-500 group-hover:scale-125 group-hover:opacity-100"
        />
      ))}
    </div>
  );
}

/** Privacy Activity History — ticks rise like a log filling in. */
function HistoryTicks() {
  const stagger = useStagger();
  return (
    <div className="flex h-6 items-end gap-[5px]" aria-hidden="true">
      {Array.from({ length: 9 }, (_, i) => (
        <span
          key={i}
          style={stagger(i, 45)}
          className="h-1.5 w-[3px] rounded-pill bg-border-strong transition-all duration-300
                     group-hover:h-5 group-hover:bg-accent/60"
        />
      ))}
    </div>
  );
}

/* ------------------------------------------------------------- wide visuals */

/** AI Exposure Detection — a live match readout under a scanline. */
function MatchReadout() {
  const stagger = useStagger();
  const rows = [
    { field: "Email",    where: "4 sources", confidence: "94%", tone: "text-danger" },
    { field: "Phone",    where: "3 sources", confidence: "88%", tone: "text-danger" },
    { field: "Name + City", where: "5 sources", confidence: "71%", tone: "text-warning" },
    { field: "Employer", where: "1 source",  confidence: "40%", tone: "text-muted" },
  ];
  return (
    <div className="relative mt-5 overflow-hidden rounded-[10px] border border-border bg-bg/70 p-3">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-12 animate-scan-sweep bg-gradient-to-b from-transparent via-accent/10 to-transparent" />
      <div className="relative flex items-center justify-between">
        <span className="label">match readout</span>
        <span className="mono text-[10px] text-accent">12 matched</span>
      </div>
      <ul className="relative mt-2.5 space-y-2">
        {rows.map((r, i) => (
          <li key={r.field} className="flex items-center gap-3">
            <span className="w-24 shrink-0 truncate text-[12px]">{r.field}</span>
            <span className="h-1 flex-1 overflow-hidden rounded-pill bg-elevated">
              <span
                style={{ ...stagger(i, 90), "--w": r.confidence } as CSSProperties}
                className="block h-full w-[10%] bg-accent/70 transition-[width] duration-500 ease-out group-hover:w-[var(--w)]"
              />
            </span>
            <span className={`mono w-16 shrink-0 text-right text-[11px] ${r.tone}`}>{r.where}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Automated Privacy Requests — the stage tracker for one live request. */
function RequestPipeline() {
  const stagger = useStagger();
  const stages = ["Drafted", "Sent", "Awaiting", "Closed"];
  const reached = 2; // index of the current stage

  return (
    <div className="mt-5 rounded-[10px] border border-border bg-bg/70 p-3">
      <div className="flex items-center justify-between">
        <span className="label">request · northgate directory</span>
        <span className="mono text-[10px] text-warning">28d left</span>
      </div>

      <div className="relative mt-4">
        <span className="absolute left-0 right-0 top-[5px] h-px bg-border" aria-hidden="true" />
        <span
          className="absolute left-0 top-[5px] h-px w-[12%] bg-accent transition-[width] duration-700 ease-out group-hover:w-2/3"
          aria-hidden="true"
        />
        <ul className="relative flex justify-between">
          {stages.map((s, i) => (
            <li key={s} className="flex flex-col items-center gap-2">
              <span
                style={stagger(i, 100)}
                className={`h-[11px] w-[11px] rounded-full border-2 transition-colors duration-300 ${
                  i <= reached
                    ? "border-accent bg-bg group-hover:bg-accent"
                    : "border-border bg-bg"
                }`}
              />
              <span className={`mono text-[10px] ${i <= reached ? "text-text" : "text-faint"}`}>{s}</span>
            </li>
          ))}
        </ul>
      </div>

      <p className="mt-3 text-[12px] leading-relaxed text-muted">
        Drafted against the right legal basis, sent to the named contact, then chased on the clock.
      </p>
    </div>
  );
}

/* --------------------------------------------------------------------- grid */

interface FeatureItem {
  title: string;
  description: string;
  icon: LucideIcon;
  /** Wide cards carry a full inline readout; compact ones a single micro-visual. */
  wide?: boolean;
  visual: ReactNode;
}

const FEATURES: FeatureItem[] = [
  {
    title: "AI Exposure Detection",
    description:
      "Reads public sources the way an attacker would, then tells you which fragments of you are actually findable — and how confident it is.",
    icon: ScanSearch,
    wide: true,
    visual: <MatchReadout />,
  },
  {
    title: "Automated Privacy Requests",
    description:
      "Drafts the removal or erasure request each source actually accepts, sends it, and tracks the response window for you.",
    icon: Send,
    wide: true,
    visual: <RequestPipeline />,
  },
  {
    title: "Data Broker Discovery",
    description: "Finds the resellers holding a copy of your record, including the ones you never signed up with.",
    icon: Database,
    visual: <BrokerCells />,
  },
  {
    title: "Breach Monitoring",
    description: "Cross-checks your identifiers against known breach corpora and flags what needs rotating.",
    icon: ShieldAlert,
    visual: <BreachSpark />,
  },
  {
    title: "Risk Prioritisation",
    description: "Ranks every finding by real-world harm, so you fix the four that matter before the forty that don't.",
    icon: ListFilter,
    visual: <RiskBars />,
  },
  {
    title: "Removal Tracking",
    description: "Every request has a state and a deadline. Nothing sits in limbo without someone noticing.",
    icon: Activity,
    visual: <RemovalTrack />,
  },
  {
    title: "Continuous Monitoring",
    description: "Removed data has a habit of returning. Scheduled sweeps catch reappearances and re-open the case.",
    icon: Radar,
    visual: <MonitorRings />,
  },
  {
    title: "Privacy Activity History",
    description: "A timestamped log of what was found, what was sent, and what came back — exportable, and yours.",
    icon: Clock,
    visual: <HistoryTicks />,
  },
];

export default function Features({ className = "" }: FeaturesProps) {
  return (
    <Section
      id="features"
      className={className}
      label="Capabilities"
      title="A privacy team, compressed into one product."
      lead="Detection, action, and follow-through. Each part does one job well and hands off to the next."
    >
      <div className="grid gap-3 sm:gap-4 md:grid-cols-2 lg:grid-cols-6">
        {FEATURES.map((feature, index) => {
          const Icon = feature.icon;
          return (
            <Reveal
              key={feature.title}
              delay={index}
              className={feature.wide ? "md:col-span-2 lg:col-span-3" : "lg:col-span-2"}
            >
              <article
                className={`group card card-hover flex h-full flex-col p-5 ${
                  feature.wide ? "sm:p-6" : ""
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <span
                    className="grid h-9 w-9 shrink-0 place-items-center rounded-[10px] border border-border
                               bg-elevated text-muted transition-colors duration-300
                               group-hover:border-accent/40 group-hover:bg-accent/10 group-hover:text-accent"
                  >
                    <Icon className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <span className="mono text-[10px] tracking-[0.18em] text-faint">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                </div>

                <h3 className={`mt-4 font-semibold tracking-tight ${feature.wide ? "text-lg" : "text-[15px]"}`}>
                  {feature.title}
                </h3>
                <p className={`mt-2 flex-1 leading-relaxed text-muted ${feature.wide ? "text-sm sm:text-[15px]" : "text-sm"}`}>
                  {feature.description}
                </p>

                {feature.wide ? feature.visual : <div className="mt-5 flex h-6 items-end">{feature.visual}</div>}
              </article>
            </Reveal>
          );
        })}
      </div>
    </Section>
  );
}
