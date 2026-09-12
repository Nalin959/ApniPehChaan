import { useCountUp } from "../lib/hooks";
import { runMockScan } from "../data/mock";
import type { ScanResult } from "../lib/types";

export interface TrustStatsProps {
  /**
   * Live counts when a scan has run. Defaults to the same dataset the console
   * scans, so the strip can never contradict the number shown above it.
   */
  result?: ScanResult | null;
  className?: string;
}

/** Computed once — the baseline is static and re-deriving it per render is waste. */
const BASELINE = runMockScan("preview@privacy.ai").counts;

/** Removal requests in flight across the demo account. */
const REMOVAL_REQUESTS = 8;

function pad2(n: number) {
  return String(n).padStart(2, "0");
}

interface StatCellProps {
  value: number;
  label: string;
  tone?: string;
}

function CountCell({ value, label, tone = "text-text" }: StatCellProps) {
  const { ref, value: shown } = useCountUp(value);
  return (
    <div className="bg-bg px-4 py-6 sm:px-6 sm:py-8">
      <div className={`mono text-[clamp(1.75rem,5vw,2.5rem)] font-bold leading-none tracking-tight ${tone}`}>
        {/* The ref must sit on the element that scrolls into view for the counter to arm. */}
        <span ref={ref}>{pad2(shown)}</span>
      </div>
      <div className="label mt-3 leading-relaxed">{label}</div>
    </div>
  );
}

function LiteralCell({ value, label }: { value: string; label: string }) {
  return (
    <div className="bg-bg px-4 py-6 sm:px-6 sm:py-8">
      <div className="mono text-[clamp(1.75rem,5vw,2.5rem)] font-bold leading-none tracking-tight text-accent">
        {value}
      </div>
      <div className="label mt-3 leading-relaxed">{label}</div>
    </div>
  );
}

export default function TrustStats({ result, className = "" }: TrustStatsProps) {
  const counts = result?.counts ?? BASELINE;

  return (
    <section aria-label="Protection at a glance" className={`border-y border-border ${className}`}>
      <div className="container-x !px-0 sm:!px-0">
        {/* gap-px over a border-coloured ground draws hairlines that reflow with
            the grid, so 2-up and 4-up need no per-cell border juggling. */}
        <div className="grid grid-cols-2 gap-px bg-border md:grid-cols-4">
          <CountCell value={counts.total} label="Exposure sources" />
          <CountCell value={counts.high} label="High-risk findings" tone="text-danger" />
          <CountCell value={REMOVAL_REQUESTS} label="Removal requests" />
          <LiteralCell value="24/7" label="Monitoring" />
        </div>
      </div>
    </section>
  );
}
