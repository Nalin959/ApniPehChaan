import { useRef, useState } from "react";
import type { KeyboardEvent, ReactNode } from "react";
import {
  Activity, ChartColumn, CircleCheck, Clock, Database, LayoutDashboard,
  Radar, Send, ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Pill, Reveal, Section, StatusDot } from "../lib/ui";
import { useCountUp, useInViewOnce, usePrefersReducedMotion } from "../lib/hooks";
import { mockDataSources, mockRemovalRequests, riskBg } from "../data/mock";

/** DashboardPreview takes no props — it renders a self-contained demo console. */
export interface DashboardPreviewProps {
  className?: string;
}

type TabId = "overview" | "exposure" | "requests" | "monitoring";

interface TabDef {
  id: TabId;
  label: string;
  icon: LucideIcon;
  /** Shown in the console's fake address bar, so switching tabs feels like routing. */
  route: string;
}

const TABS: TabDef[] = [
  { id: "overview",   label: "Overview",   icon: LayoutDashboard, route: "overview" },
  { id: "exposure",   label: "Exposure",   icon: Database,        route: "exposure/sources" },
  { id: "requests",   label: "Requests",   icon: Send,            route: "requests/open" },
  { id: "monitoring", label: "Monitoring", icon: Radar,           route: "monitoring" },
];

/**
 * The console shows a curated snapshot rather than deriving counts from the mock
 * source list — the demo narrative is a 12-source account, and the numbers have
 * to agree with what the rest of the page says out loud.
 */
const EXPOSURE = { total: 12, high: 4, medium: 5, low: 3 } as const;

const SCORE = { value: 62, max: 100, target: 85 } as const;

interface ActivityRow {
  time: string;
  message: string;
}

const ACTIVITY: ActivityRow[] = [
  { time: "09:41", message: "Removal request submitted" },
  { time: "09:38", message: "Exposure detected" },
  { time: "09:36", message: "Source analysed" },
  { time: "09:21", message: "Data removed" },
];

/* ------------------------------------------------------------------ pieces */

function PanelCard({
  title, icon: Icon, children, className = "",
}: { title: string; icon: LucideIcon; children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-[10px] border border-border bg-bg/50 p-4 ${className}`}>
      <div className="mb-3 flex items-center gap-2">
        <Icon className="h-3.5 w-3.5 text-faint" aria-hidden="true" />
        <span className="label">{title}</span>
      </div>
      {children}
    </div>
  );
}

/** Radial score. Amber, not green — 62/100 is a warning, and colour should say so. */
function ScoreRing() {
  const { ref, seen } = useInViewOnce<SVGSVGElement>();
  const { ref: numRef, value } = useCountUp(SCORE.value);
  const circumference = 2 * Math.PI * 52;
  const offset = circumference * (1 - SCORE.value / SCORE.max);

  return (
    <div className="flex items-center gap-4">
      <div className="relative shrink-0">
        <svg ref={ref} viewBox="0 0 120 120" className="h-[92px] w-[92px] -rotate-90" aria-hidden="true">
          <circle cx="60" cy="60" r="52" fill="none" stroke="rgb(var(--border))" strokeWidth="9" />
          <circle
            cx="60" cy="60" r="52" fill="none"
            stroke="rgb(var(--warning))" strokeWidth="9" strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={seen ? offset : circumference}
            className="transition-[stroke-dashoffset] duration-1000 ease-out"
            style={{ filter: "drop-shadow(0 0 7px rgb(var(--warning) / .35))" }}
          />
        </svg>
        <div className="absolute inset-0 grid place-items-center">
          <div className="text-center leading-none">
            <span ref={numRef} className="mono text-2xl font-bold">{value}</span>
            <span className="mono text-xs text-faint">/{SCORE.max}</span>
          </div>
        </div>
      </div>
      <div className="min-w-0">
        <div className="text-sm font-semibold">Needs attention</div>
        <p className="mt-1 text-xs leading-relaxed text-muted">
          Four high-risk sources are holding the score down.
        </p>
        <div className="mono mt-2 text-[11px] text-faint">
          Target <span className="text-accent">{SCORE.target}</span> after open requests clear
        </div>
      </div>
    </div>
  );
}

function ExposureBars() {
  const { ref, seen } = useInViewOnce<HTMLDivElement>();
  const { ref: numRef, value } = useCountUp(EXPOSURE.total, 900);
  const rows = [
    { label: "High",   count: EXPOSURE.high,   bar: "bg-danger",  text: "text-danger" },
    { label: "Medium", count: EXPOSURE.medium, bar: "bg-warning", text: "text-warning" },
    { label: "Low",    count: EXPOSURE.low,    bar: "bg-accent",  text: "text-accent" },
  ];

  return (
    <div ref={ref}>
      <div className="flex items-baseline gap-2">
        <span ref={numRef} className="mono text-2xl font-bold leading-none">{value}</span>
        <span className="label">sources</span>
      </div>

      {/* Stacked proportion bar — the whole exposure at a glance, one row tall. */}
      <div className="mt-3 flex h-1.5 w-full gap-px overflow-hidden rounded-pill bg-elevated">
        {rows.map((r) => (
          <span
            key={r.label}
            className={`${r.bar} h-full transition-[width] duration-700 ease-out`}
            style={{ width: seen ? `${(r.count / EXPOSURE.total) * 100}%` : "0%" }}
          />
        ))}
      </div>

      <ul className="mt-3 space-y-1.5">
        {rows.map((r) => (
          <li key={r.label} className="flex items-center gap-2">
            <span className={`mono w-14 text-[11px] uppercase tracking-wider ${r.text}`}>{r.label}</span>
            <span className="h-1 flex-1 overflow-hidden rounded-pill bg-elevated">
              <span
                className={`block h-full ${r.bar} transition-[width] duration-700 ease-out`}
                style={{ width: seen ? `${(r.count / EXPOSURE.total) * 100}%` : "0%" }}
              />
            </span>
            <span className="mono w-4 text-right text-[11px] text-muted">{r.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function MonitoringBlock({ dense = false }: { dense?: boolean }) {
  const daysElapsed = 16;
  const cycle = 30;
  return (
    <div>
      <div className="flex items-center gap-2">
        <StatusDot tone="accent" />
        <span className="mono text-sm font-bold tracking-wide text-accent">ACTIVE</span>
      </div>
      <div className="mono mt-3 text-[13px] text-text">
        Next scan: <span className="font-bold">14 days</span>
      </div>
      {/* One tick per day of the cycle: elapsed days read solid, the rest hollow. */}
      <div className="mt-3 flex gap-[3px]" aria-hidden="true">
        {Array.from({ length: cycle }, (_, i) => (
          <span
            key={i}
            className={`h-4 w-[3px] rounded-pill ${i < daysElapsed ? "bg-accent/70" : "bg-elevated"}`}
          />
        ))}
      </div>
      <div className="mono mt-2 text-[10px] text-faint">day {daysElapsed} of {cycle}</div>
      {!dense && (
        <p className="mt-3 text-xs leading-relaxed text-muted">
          Sources that reappear between scans raise an alert instead of waiting for the cycle.
        </p>
      )}
    </div>
  );
}

function ActivityFeed() {
  return (
    <div>
      <ul className="space-y-2.5">
        {ACTIVITY.map((row) => (
          <li key={row.message} className="flex items-start gap-2.5">
            <CircleCheck className="mt-px h-3.5 w-3.5 shrink-0 text-accent" aria-hidden="true" />
            <span className="min-w-0 flex-1 text-[13px] leading-snug text-text">{row.message}</span>
            <span className="mono shrink-0 text-[11px] text-faint">{row.time}</span>
          </li>
        ))}
      </ul>
      <div className="mono mt-3 flex items-center gap-2 border-t border-border pt-3 text-[11px] text-faint">
        <span>watching</span>
        <span className="inline-block h-3 w-1.5 bg-accent/70 animate-blink" aria-hidden="true" />
      </div>
    </div>
  );
}

const STAGE_TONE: Record<string, string> = {
  generated: "border-info/30 bg-info/10 text-info",
  sent:      "border-warning/30 bg-warning/10 text-warning",
  awaiting:  "border-warning/30 bg-warning/10 text-warning",
  removed:   "border-accent/30 bg-accent/10 text-accent",
  found:     "border-border bg-elevated text-muted",
  analysed:  "border-border bg-elevated text-muted",
};

function RequestRows({ limit }: { limit: number }) {
  return (
    <ul className="divide-y divide-border">
      {mockRemovalRequests.slice(0, limit).map((req) => (
        <li key={req.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2.5 first:pt-0 last:pb-0">
          <span className="min-w-0 flex-1 truncate text-[13px] font-medium">{req.source}</span>
          <Pill className={STAGE_TONE[req.stage]}>{req.stage}</Pill>
          <span className="mono w-full text-[11px] text-faint sm:w-auto">
            {req.deadlineDays ? `${req.deadlineDays}d left` : req.submitted}
          </span>
        </li>
      ))}
    </ul>
  );
}

/* ------------------------------------------------------------------ panels */

function OverviewPanel() {
  return (
    <div className="grid gap-3 lg:grid-cols-3">
      <PanelCard title="Privacy score" icon={ChartColumn}><ScoreRing /></PanelCard>
      <PanelCard title="Exposure" icon={Database}><ExposureBars /></PanelCard>
      <PanelCard title="Monitoring" icon={Radar}><MonitoringBlock dense /></PanelCard>
      <PanelCard title="Recent activity" icon={Activity} className="lg:col-span-2">
        <ActivityFeed />
      </PanelCard>
      <PanelCard title="Requests in flight" icon={Send}><RequestRows limit={3} /></PanelCard>
    </div>
  );
}

function ExposurePanel() {
  return (
    <div className="rounded-[10px] border border-border bg-bg/50">
      <div className="hidden grid-cols-[1.4fr_1fr_auto] gap-3 border-b border-border px-4 py-2.5 sm:grid">
        <span className="label">Source</span>
        <span className="label">Exposed fields</span>
        <span className="label text-right">Risk</span>
      </div>
      <ul className="divide-y divide-border">
        {mockDataSources.slice(0, 6).map((src) => (
          <li
            key={src.id}
            className="grid gap-1 px-4 py-3 transition-colors hover:bg-elevated/60 sm:grid-cols-[1.4fr_1fr_auto] sm:items-center sm:gap-3"
          >
            <div className="min-w-0">
              <div className="truncate text-[13px] font-medium">{src.name}</div>
              <div className="mono text-[10px] uppercase tracking-[0.14em] text-faint">{src.category}</div>
            </div>
            <div className="mono truncate text-[11px] text-muted">{src.exposed.join(" · ")}</div>
            <div className="sm:text-right">
              <Pill className={riskBg[src.risk]}>{src.risk}</Pill>
            </div>
          </li>
        ))}
      </ul>
      <div className="mono border-t border-border px-4 py-2.5 text-[11px] text-faint">
        showing 6 of {EXPOSURE.total} · sorted by risk
      </div>
    </div>
  );
}

function RequestsPanel() {
  return (
    <div className="grid gap-3 lg:grid-cols-3">
      <div className="rounded-[10px] border border-border bg-bg/50 p-4 lg:col-span-2">
        <div className="mb-3 flex items-center gap-2">
          <Send className="h-3.5 w-3.5 text-faint" aria-hidden="true" />
          <span className="label">Open requests</span>
        </div>
        <RequestRows limit={4} />
      </div>
      <div className="space-y-3">
        <PanelCard title="Response window" icon={Clock}>
          <div className="mono text-2xl font-bold leading-none">27<span className="text-sm text-faint">d</span></div>
          <p className="mt-2 text-xs leading-relaxed text-muted">
            Median time left before the earliest statutory deadline on an open request.
          </p>
        </PanelCard>
        <PanelCard title="Outcomes" icon={CircleCheck}>
          <ul className="mono space-y-1.5 text-[12px]">
            <li className="flex justify-between"><span className="text-muted">Removed</span><span className="text-accent">1</span></li>
            <li className="flex justify-between"><span className="text-muted">Awaiting</span><span className="text-warning">2</span></li>
            <li className="flex justify-between"><span className="text-muted">Drafted</span><span className="text-info">1</span></li>
          </ul>
        </PanelCard>
      </div>
    </div>
  );
}

function MonitoringPanel() {
  const watched = ["Email", "Phone", "Name", "Address", "Employer"];
  return (
    <div className="grid gap-3 lg:grid-cols-3">
      <PanelCard title="Status" icon={Radar} className="lg:col-span-1"><MonitoringBlock /></PanelCard>

      <PanelCard title="Watched identifiers" icon={ShieldCheck}>
        <ul className="space-y-2">
          {watched.map((w) => (
            <li key={w} className="flex items-center justify-between gap-3">
              <span className="text-[13px]">{w}</span>
              <span className="mono text-[10px] uppercase tracking-[0.14em] text-accent">watched</span>
            </li>
          ))}
        </ul>
      </PanelCard>

      <PanelCard title="Sweep" icon={Activity}>
        {/* Decorative: a scanline crossing a hairline grid, the visual shorthand
            for "the cycle is running right now". */}
        <div className="relative h-[148px] overflow-hidden rounded-[8px] border border-border bg-bg grid-bg" aria-hidden="true">
          <div className="absolute inset-x-0 top-0 h-16 animate-scan-sweep bg-gradient-to-b from-transparent via-accent/20 to-transparent" />
          <div className="absolute inset-x-0 bottom-0 p-3">
            <div className="mono text-[10px] text-faint">last sweep · 16 days ago</div>
            <div className="mono text-[10px] text-accent">0 new exposures since</div>
          </div>
        </div>
      </PanelCard>
    </div>
  );
}

/* ------------------------------------------------------------------- shell */

export default function DashboardPreview({ className = "" }: DashboardPreviewProps) {
  const [tab, setTab] = useState<TabId>("overview");
  const reduced = usePrefersReducedMotion();
  const uid = "dash";
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const onTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const moves: Record<string, number> = {
      ArrowRight: index + 1, ArrowDown: index + 1,
      ArrowLeft: index - 1, ArrowUp: index - 1,
      Home: 0, End: TABS.length - 1,
    };
    const target = moves[event.key];
    if (target === undefined) return;
    event.preventDefault();
    const next = (target + TABS.length) % TABS.length;
    setTab(TABS[next].id);
    tabRefs.current[next]?.focus();
  };

  const active = TABS.find((t) => t.id === tab) ?? TABS[0];

  return (
    <Section
      id="dashboard"
      className={className}
      label="The console"
      title={<>Everything you are exposed to,<br className="hidden sm:block" /> on one screen.</>}
      lead="Score, sources, requests and monitoring in a single view — the same surface the agent writes back to as work completes."
    >
      <Reveal>
        <div
          className={
            // The tilt is a desktop-only flourish: at phone widths a rotated
            // frame is the fastest way to create horizontal overflow.
            reduced ? "" : "md:[transform:perspective(2000px)_rotateX(3.5deg)] md:[transform-origin:top_center]"
          }
        >
          <div className="overflow-hidden rounded-card border border-border bg-surface shadow-lift">
            <div className="flex flex-col md:flex-row">
              {/* Sidebar on desktop, a scrollable tab strip on phones. */}
              <div className="shrink-0 border-b border-border bg-bg/60 md:w-[196px] md:border-b-0 md:border-r">
                <div className="flex items-center gap-2 border-b border-border px-4 py-3">
                  <span className="grid h-7 w-7 place-items-center rounded-[8px] border border-accent/30 bg-accent/10">
                    <ShieldCheck className="h-3.5 w-3.5 text-accent" aria-hidden="true" />
                  </span>
                  <span className="mono text-[11px] font-bold tracking-tight">
                    PRIVACY<span className="text-accent">//</span>AI
                  </span>
                </div>

                <div
                  role="tablist"
                  aria-label="Dashboard sections"
                  className="flex gap-1 overflow-x-auto p-2 md:flex-col md:overflow-visible"
                >
                  {TABS.map((t, i) => {
                    const selected = t.id === tab;
                    const Icon = t.icon;
                    return (
                      <button
                        key={t.id}
                        ref={(el) => { tabRefs.current[i] = el; }}
                        type="button"
                        role="tab"
                        id={`${uid}-tab-${t.id}`}
                        aria-selected={selected}
                        aria-controls={`${uid}-panel-${t.id}`}
                        tabIndex={selected ? 0 : -1}
                        onClick={() => setTab(t.id)}
                        onKeyDown={(e) => onTabKeyDown(e, i)}
                        className={`flex shrink-0 items-center gap-2 rounded-[8px] px-3 py-2 text-[13px]
                                    font-medium transition-colors md:w-full ${
                          selected
                            ? "bg-accent/10 text-accent shadow-glow-sm"
                            : "text-muted hover:bg-elevated hover:text-text"
                        }`}
                      >
                        <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                        {t.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* min-w-0 keeps long table cells from forcing the frame wider. */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-3 border-b border-border bg-bg/40 px-4 py-2.5">
                  <span className="mono truncate text-[11px] text-faint">
                    privacy://{active.route}
                  </span>
                  <span className="ml-auto flex shrink-0 items-center gap-2">
                    <Pill className="border-accent/30 bg-accent/10 text-accent">
                      <StatusDot tone="accent" /> live
                    </Pill>
                  </span>
                </div>

                <div className="p-3 sm:p-4">
                  {TABS.map((t) => (
                    <div
                      key={t.id}
                      role="tabpanel"
                      id={`${uid}-panel-${t.id}`}
                      aria-labelledby={`${uid}-tab-${t.id}`}
                      hidden={t.id !== tab}
                      tabIndex={0}
                      className="min-h-[22rem] focus-visible:outline-none"
                    >
                      {t.id === tab && (
                        <div key={tab} className={reduced ? "" : "animate-fade-up"}>
                          {t.id === "overview" && <OverviewPanel />}
                          {t.id === "exposure" && <ExposurePanel />}
                          {t.id === "requests" && <RequestsPanel />}
                          {t.id === "monitoring" && <MonitoringPanel />}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </Reveal>

      <p className="mono mt-5 text-center text-[11px] text-faint">
        interactive preview · switch sections in the sidebar
      </p>
    </Section>
  );
}
