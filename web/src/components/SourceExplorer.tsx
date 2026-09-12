/**
 * SourceExplorer — the console view: who holds your data, and what to do next.
 *
 * Rows are real <button>s rather than clickable <tr>s. A table cannot contain a
 * focusable row and an expanding full-width panel without fighting its own
 * semantics, so the layout is a list that *reads* as a table: a header strip
 * and a shared grid template above md, stacked cards below it. Nothing
 * overflows horizontally at any width.
 *
 * Every source here is fictional. Publishing findings against named real
 * companies would be defamatory, and the demo does not need it.
 */
import { useId, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, CircleAlert, Clock, ShieldCheck } from "lucide-react";
import { mockDataSources, riskBg } from "../data/mock";
import { usePrefersReducedMotion } from "../lib/hooks";
import type { DataSource, RiskLevel, SourceCategory, SourceStatus } from "../lib/types";
import { Reveal, Section } from "../lib/ui";

export type RiskFilter = "all" | RiskLevel;

export interface SourceExplorerProps {
  /** Anchor id — defaults to the value the page nav and CTAs link to. */
  id?: string;
  /** Defaults to the mock scan result. */
  sources?: DataSource[];
  /** Which risk filter is selected on first render. */
  initialRisk?: RiskFilter;
  className?: string;
}

/** One grid template, declared once, shared by the header strip and every row. */
const COLS =
  "md:grid-cols-[minmax(0,1.4fr)_minmax(0,1.6fr)_6.5rem_7.5rem_1.25rem]";

const RISK_LABEL: Record<RiskLevel, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

const STATUS_TONE: Record<SourceStatus, { label: string; cls: string }> = {
  found: { label: "Found", cls: "border-border-strong bg-elevated text-muted" },
  analysed: { label: "Analysed", cls: "border-info/30 bg-info/10 text-info" },
  requested: { label: "Requested", cls: "border-warning/30 bg-warning/10 text-warning" },
  awaiting: { label: "Awaiting", cls: "border-warning/30 bg-warning/10 text-warning" },
  removed: { label: "Removed", cls: "border-accent/30 bg-accent/10 text-accent" },
};

const CATEGORY_LABEL: Record<SourceCategory, string> = {
  "data-broker": "Data broker",
  "people-search": "People search",
  marketing: "Marketing database",
  directory: "Public directory",
  breach: "Breach database",
  "public-record": "Public record",
  social: "Social profile",
};

const FILTERS: { key: RiskFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "high", label: "High" },
  { key: "medium", label: "Medium" },
  { key: "low", label: "Low" },
];

function Badge({ children, className }: { children: ReactNode; className: string }) {
  return (
    <span
      className={`inline-flex w-fit items-center justify-center rounded-pill border px-2 py-0.5
                  font-mono text-[10px] uppercase tracking-[0.12em] ${className}`}
    >
      {children}
    </span>
  );
}

function DetailField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="label mb-1.5">{label}</dt>
      <dd className="text-sm leading-relaxed text-text">{children}</dd>
    </div>
  );
}

function SourceRow({
  source,
  open,
  onToggle,
  reduced,
  uid,
}: {
  source: DataSource;
  open: boolean;
  onToggle: () => void;
  reduced: boolean;
  uid: string;
}) {
  const btnId = `${uid}-${source.id}-btn`;
  const panelId = `${uid}-${source.id}-panel`;
  const status = STATUS_TONE[source.status];

  return (
    <li className="border-b border-border last:border-b-0">
      <button
        type="button"
        id={btnId}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={onToggle}
        className={`grid w-full grid-cols-1 gap-2 px-4 py-4 text-left transition-colors
                    hover:bg-elevated/60 md:items-center md:gap-4 md:py-3.5 ${COLS}
                    ${open ? "bg-elevated/50" : ""}`}
      >
        <span className="flex min-w-0 flex-col gap-0.5">
          <span className="mono truncate text-sm text-text">{source.name}</span>
          <span className="mono truncate text-[10px] uppercase tracking-[0.12em] text-faint">
            {CATEGORY_LABEL[source.category]}
          </span>
        </span>

        <span className="mono min-w-0 break-words text-xs leading-relaxed text-muted">
          {source.exposed.join(" · ")}
        </span>

        {/* display:contents above md folds these three back into the row grid,
            while below md they stay one wrapped badge line. */}
        <span className="flex flex-wrap items-center gap-2 md:contents">
          <Badge className={riskBg[source.risk]}>{RISK_LABEL[source.risk]}</Badge>
          <Badge className={status.cls}>{status.label}</Badge>
          <ChevronDown
            aria-hidden="true"
            className={`ml-auto h-4 w-4 shrink-0 text-faint transition-transform duration-300
                        ${open ? "rotate-180 text-accent" : ""}`}
          />
        </span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key={panelId}
            id={panelId}
            role="region"
            aria-labelledby={btnId}
            initial={reduced ? false : { height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: reduced ? 0 : 0.32, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <div className="border-t border-border bg-bg/50 px-4 py-5">
              <p className="mb-5 max-w-2xl text-sm leading-relaxed text-muted">{source.detail}</p>

              <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                <DetailField label="Source">
                  {source.name}
                  <span className="mono block text-xs text-faint">
                    {CATEGORY_LABEL[source.category]}
                  </span>
                </DetailField>

                <DetailField label="Information exposed">
                  <span className="flex flex-wrap gap-1.5">
                    {source.exposed.map((field) => (
                      <span
                        key={field}
                        className="mono rounded-pill border border-border bg-elevated px-2 py-0.5
                                   text-[11px] text-text"
                      >
                        {field}
                      </span>
                    ))}
                  </span>
                </DetailField>

                <DetailField label="Risk level">
                  <span className="inline-flex items-center gap-2">
                    <CircleAlert
                      aria-hidden="true"
                      className={`h-4 w-4 ${
                        source.risk === "high"
                          ? "text-danger"
                          : source.risk === "medium"
                            ? "text-warning"
                            : "text-accent"
                      }`}
                    />
                    {RISK_LABEL[source.risk]}
                  </span>
                </DetailField>

                <DetailField label="Discovery date">
                  <span className="inline-flex items-center gap-2">
                    <Clock aria-hidden="true" className="h-4 w-4 text-faint" />
                    <span className="mono text-sm">{source.discovered}</span>
                  </span>
                </DetailField>

                <DetailField label="Recommended action">{source.recommendedAction}</DetailField>

                <DetailField label="Removal status">
                  <span className="inline-flex items-center gap-2">
                    <ShieldCheck
                      aria-hidden="true"
                      className={`h-4 w-4 ${
                        source.status === "removed" ? "text-accent" : "text-faint"
                      }`}
                    />
                    {status.label}
                  </span>
                </DetailField>
              </dl>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  );
}

export function SourceExplorer({
  id = "exposure-scan",
  sources = mockDataSources,
  initialRisk = "all",
  className = "",
}: SourceExplorerProps) {
  const reduced = usePrefersReducedMotion();
  // React's generated ids carry delimiters; strip them so the id is safe anywhere.
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [risk, setRisk] = useState<RiskFilter>(initialRisk);
  const [openId, setOpenId] = useState<string | null>(null);

  const counts = useMemo(
    () => ({
      all: sources.length,
      high: sources.filter((s) => s.risk === "high").length,
      medium: sources.filter((s) => s.risk === "medium").length,
      low: sources.filter((s) => s.risk === "low").length,
    }),
    [sources],
  );

  const visible = useMemo(
    () => (risk === "all" ? sources : sources.filter((s) => s.risk === risk)),
    [sources, risk],
  );

  return (
    <Section
      id={id}
      className={className}
      label="Exposure scan"
      title="Who has your data?"
      lead="Fourteen sources matched against your identity. Open any row for what is exposed,
            why it matters and the request that clears it."
    >
      <Reveal>
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap gap-2" role="group" aria-label="Filter sources by risk">
            {FILTERS.map((f) => {
              const selected = risk === f.key;
              return (
                <button
                  key={f.key}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => {
                    setRisk(f.key);
                    setOpenId(null); // a row hidden by the filter must not stay "open"
                  }}
                  className={`inline-flex items-center gap-2 rounded-pill border px-3 py-1.5
                              font-mono text-[11px] uppercase tracking-[0.12em]
                              transition-colors duration-200
                              ${selected
                                ? "border-accent/40 bg-accent/10 text-accent"
                                : "border-border bg-surface text-muted hover:border-border-strong hover:text-text"}`}
                >
                  {f.label}
                  <span className={selected ? "text-accent/70" : "text-faint"}>
                    {counts[f.key]}
                  </span>
                </button>
              );
            })}
          </div>

          <p className="mono text-[11px] text-faint" aria-live="polite">
            {visible.length} of {sources.length} sources shown
          </p>
        </div>

        <div className="card overflow-hidden p-0">
          <div
            className={`hidden gap-4 border-b border-border-strong px-4 py-3 md:grid ${COLS}`}
            aria-hidden="true"
          >
            <span className="label">Source</span>
            <span className="label">Data</span>
            <span className="label">Risk</span>
            <span className="label">Status</span>
            <span />
          </div>

          {visible.length === 0 ? (
            <p className="px-4 py-10 text-center text-sm text-muted">
              No sources match this filter.
            </p>
          ) : (
            <ul>
              {visible.map((source) => (
                <SourceRow
                  key={source.id}
                  source={source}
                  uid={uid}
                  reduced={reduced}
                  open={openId === source.id}
                  onToggle={() => setOpenId((cur) => (cur === source.id ? null : source.id))}
                />
              ))}
            </ul>
          )}
        </div>

        <p className="mt-4 text-xs leading-relaxed text-faint">
          All sources shown are fictional and used to demonstrate the interface.
        </p>
      </Reveal>
    </Section>
  );
}

export default SourceExplorer;
