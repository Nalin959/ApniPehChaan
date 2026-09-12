import { ArrowRight, RotateCcw, TriangleAlert } from "lucide-react";
import { Pill, Reveal, Section } from "../lib/ui";
import { riskBg } from "../data/mock";
import type { DataSource, ScanResult } from "../lib/types";

export interface ScanResultsProps {
  /** Null renders nothing, so the parent can mount this unconditionally if it prefers. */
  result: ScanResult | null;
  /** Clears the scan and returns the visitor to the hero form. */
  onRescan?: () => void;
}

function pad2(n: number) {
  return String(n).padStart(2, "0");
}

const SPLIT: { key: "high" | "medium" | "low"; label: string; tone: string }[] = [
  { key: "high", label: "High risk", tone: "text-danger" },
  { key: "medium", label: "Medium risk", tone: "text-warning" },
  { key: "low", label: "Low risk", tone: "text-accent" },
];

function FindingCard({ source, index }: { source: DataSource; index: number }) {
  return (
    <Reveal delay={index + 1} className="h-full">
      <article className="card card-hover flex h-full flex-col p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="truncate text-[15px] font-semibold tracking-tight text-text">
              {source.name}
            </h3>
            <p className="label mt-1.5">{source.category.replace(/-/g, " ")}</p>
          </div>
          <span
            className={`shrink-0 rounded-pill border px-2.5 py-1 font-mono text-[9px] uppercase
                        tracking-[0.14em] ${riskBg[source.risk]}`}
          >
            {source.risk}
          </span>
        </div>

        <div className="mt-4">
          <p className="label mb-2">Exposed</p>
          <ul className="flex flex-wrap gap-1.5">
            {source.exposed.map((field) => (
              <li key={field}>
                <Pill className="border-border bg-elevated/70 text-muted">{field}</Pill>
              </li>
            ))}
          </ul>
        </div>

        {/* mt-auto pins the action to the bottom so cards of different heights align. */}
        <div className="mt-auto flex items-start gap-2.5 border-t border-border pt-4 text-[13px] leading-relaxed text-muted">
          <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" aria-hidden />
          <span>{source.recommendedAction}</span>
        </div>
      </article>
    </Reveal>
  );
}

export default function ScanResults({ result, onRescan }: ScanResultsProps) {
  if (!result) return null;

  const { counts, email, sources } = result;
  const topFindings = sources.filter((s) => s.risk === "high").slice(0, 3);

  return (
    <Section className="!pt-16 sm:!pt-20">
      <Reveal>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <span className="label text-accent">SCAN COMPLETE</span>
          <span className="break-all font-mono text-[11px] text-faint">{email}</span>
        </div>

        <h2 className="mt-5 max-w-3xl text-headline font-extrabold">
          We found <span className="text-accent">{counts.total} sources</span> holding your
          personal data.
        </h2>

        <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted sm:text-lg">
          {counts.high} of them are high risk — they pair your name with something directly
          contactable. Those are the ones worth removing first.
        </p>
      </Reveal>

      <Reveal delay={1}>
        <dl className="mt-10 grid grid-cols-3 gap-px overflow-hidden rounded-card border border-border bg-border">
          {SPLIT.map((s) => (
            <div key={s.key} className="bg-surface px-3 py-5 text-center sm:px-5 sm:py-6">
              <dd className={`mono text-[clamp(1.5rem,4.5vw,2.25rem)] font-bold leading-none ${s.tone}`}>
                {pad2(counts[s.key])}
              </dd>
              <dt className="label mt-2.5">{s.label}</dt>
            </div>
          ))}
        </dl>
      </Reveal>

      <div className="mt-12">
        <Reveal>
          <h3 className="label mb-5">Top high-risk findings</h3>
        </Reveal>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {topFindings.map((source, i) => (
            <FindingCard key={source.id} source={source} index={i} />
          ))}
        </div>
      </div>

      <Reveal delay={4}>
        <div className="mt-10 flex flex-wrap items-center gap-3">
          <a href="#exposure-scan" className="btn-primary px-6 py-3">
            View Full Exposure Report
            <ArrowRight className="h-4 w-4" aria-hidden />
          </a>
          <a href="#protection" className="btn-ghost px-6 py-3">
            Start Removal
            <ArrowRight className="h-4 w-4" aria-hidden />
          </a>
          {onRescan && (
            <button
              type="button"
              onClick={onRescan}
              className="inline-flex items-center gap-2 px-2 py-3 text-[13px] font-medium text-faint
                         transition-colors duration-200 hover:text-text"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden />
              Scan another address
            </button>
          )}
        </div>
      </Reveal>
    </Section>
  );
}
