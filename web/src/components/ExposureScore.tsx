/**
 * ExposureScore — the headline number, built as an instrument rather than a
 * statistic. The ring is plain SVG stroke geometry so it animates on the
 * compositor and scales with its container; the number counts up because a
 * gauge that arrives already settled reads as a static image.
 *
 * Every animation here is decoration over information that is also present in
 * text and ARIA, so reduced motion simply skips to the final state.
 */
import { ArrowRight } from "lucide-react";
import { mockPrivacyScore } from "../data/mock";
import { useCountUp, useInViewOnce, usePrefersReducedMotion } from "../lib/hooks";
import type { ExposureBreakdownItem, PrivacyScore, RiskLevel } from "../lib/types";
import { Reveal, Section } from "../lib/ui";

export interface ExposureScoreProps {
  /** Anchor id, so a nav can link straight to the score. */
  id?: string;
  /** Defaults to the mock scan result. */
  score?: PrivacyScore;
  className?: string;
  /** Supply a handler to make the CTA a button; otherwise it links to `reportHref`. */
  onViewReport?: () => void;
  /** Where the CTA points when no handler is given. */
  reportHref?: string;
}

/** Ring geometry. The viewBox is square so the gauge stays circular at any size. */
const VB = 240;
const CENTRE = VB / 2;
const R = 86;
const CIRC = 2 * Math.PI * R;
const TICKS = 60;

interface Tone {
  stroke: string;
  text: string;
  badge: string;
  segment: string;
}

/**
 * Colour follows the reported level, not the raw number — the level is the
 * judgement, and a future scoring change must not silently recolour the ring.
 */
const LEVEL_TONE: Record<PrivacyScore["level"], Tone> = {
  Low: {
    stroke: "stroke-accent",
    text: "text-accent",
    badge: "border-accent/30 bg-accent/10 text-accent",
    segment: "bg-accent",
  },
  Moderate: {
    stroke: "stroke-warning",
    text: "text-warning",
    badge: "border-warning/30 bg-warning/10 text-warning",
    segment: "bg-warning",
  },
  High: {
    stroke: "stroke-danger",
    text: "text-danger",
    badge: "border-danger/30 bg-danger/10 text-danger",
    segment: "bg-danger",
  },
  Critical: {
    stroke: "stroke-danger",
    text: "text-danger",
    badge: "border-danger/30 bg-danger/10 text-danger",
    segment: "bg-danger",
  },
};

const RISK_SEGMENT: Record<RiskLevel, string> = {
  high: "bg-danger",
  medium: "bg-warning",
  low: "bg-accent",
};

const RISK_TEXT: Record<RiskLevel, string> = {
  high: "text-danger",
  medium: "text-warning",
  low: "text-accent",
};

const SEGMENTS = 24;

function BreakdownBar({
  item,
  index,
  active,
  reduced,
}: {
  item: ExposureBreakdownItem;
  index: number;
  active: boolean;
  reduced: boolean;
}) {
  const filled = Math.round((item.value / 100) * SEGMENTS);
  const tone = RISK_SEGMENT[item.risk];
  const text = RISK_TEXT[item.risk];

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
      <div className="flex items-center justify-between gap-3 sm:w-44 sm:shrink-0">
        <span className="text-sm text-muted">{item.label}</span>
        <span className={`mono text-sm font-semibold sm:hidden ${text}`}>{item.value}</span>
      </div>

      <div
        role="progressbar"
        aria-label={`${item.label} — ${item.risk} risk`}
        aria-valuenow={item.value}
        aria-valuemin={0}
        aria-valuemax={100}
        className="flex min-w-0 flex-1 items-center gap-[3px]"
      >
        {Array.from({ length: SEGMENTS }, (_, k) => {
          const lit = active && k < filled;
          return (
            <span
              key={k}
              aria-hidden="true"
              className={`h-5 min-w-0 flex-1 rounded-[2px] transition-all duration-300 ease-out
                          ${lit ? `${tone} opacity-100` : "bg-border-strong/30 opacity-60"}`}
              style={
                reduced ? undefined : { transitionDelay: `${index * 90 + k * 22}ms` }
              }
            />
          );
        })}
      </div>

      <span className={`mono hidden w-9 text-right text-sm font-semibold sm:block ${text}`}>
        {item.value}
      </span>
    </div>
  );
}

export function ExposureScore({
  id = "exposure-score",
  score = mockPrivacyScore,
  className = "",
  onViewReport,
  reportHref = "#exposure-scan",
}: ExposureScoreProps) {
  const reduced = usePrefersReducedMotion();
  const { ref: panelRef, seen } = useInViewOnce<HTMLDivElement>();
  const { ref: numberRef, value } = useCountUp(score.score);

  const tone = LEVEL_TONE[score.level];
  const ratio = Math.max(0, Math.min(1, score.score / score.max));
  const settled = seen || reduced;
  const dashoffset = settled ? CIRC * (1 - ratio) : CIRC;
  const levelLabel = `${score.level.toUpperCase()} RISK`;

  const cta = (
    <>
      View Full Exposure Report
      <ArrowRight className="h-4 w-4" aria-hidden="true" />
    </>
  );

  return (
    <Section
      id={id}
      className={className}
      label="Privacy exposure"
      title="One number for how findable you are."
      lead="Scored across the signals that let a stranger reach you, profile you or impersonate
            you — then broken down so you can see which part is doing the damage."
    >
      <Reveal>
        <div
          ref={panelRef}
          className="card grid gap-8 p-5 sm:p-8 lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)] lg:gap-12"
        >
          {/* Gauge */}
          <div className="flex flex-col items-center justify-center">
            <div
              role="img"
              aria-label={`Privacy exposure score ${score.score} out of ${score.max}. Level: ${score.level} risk.`}
              className="relative w-full max-w-[300px]"
            >
              <svg
                viewBox={`0 0 ${VB} ${VB}`}
                preserveAspectRatio="xMidYMid meet"
                aria-hidden="true"
                focusable="false"
                className="h-auto w-full"
              >
                <g transform={`rotate(-90 ${CENTRE} ${CENTRE})`}>
                  {/* Graticule: lit ticks give the ring a scale to be read against. */}
                  {Array.from({ length: TICKS }, (_, i) => {
                    const angle = (i / TICKS) * Math.PI * 2;
                    const lit = settled && i / TICKS < ratio;
                    const inner = 104;
                    const outer = i % 5 === 0 ? 112 : 109;
                    return (
                      <line
                        key={i}
                        x1={CENTRE + Math.cos(angle) * inner}
                        y1={CENTRE + Math.sin(angle) * inner}
                        x2={CENTRE + Math.cos(angle) * outer}
                        y2={CENTRE + Math.sin(angle) * outer}
                        strokeWidth={1}
                        className={lit ? tone.stroke : "stroke-border-strong"}
                        opacity={lit ? 0.75 : 0.35}
                        style={reduced ? undefined : { transition: `opacity 600ms ${i * 14}ms` }}
                      />
                    );
                  })}

                  <circle
                    cx={CENTRE}
                    cy={CENTRE}
                    r={R}
                    fill="none"
                    strokeWidth={12}
                    className="stroke-border-strong"
                    opacity={0.35}
                  />

                  {/* Blurred twin behind the arc: a soft bloom, not a neon outline. */}
                  <circle
                    cx={CENTRE}
                    cy={CENTRE}
                    r={R}
                    fill="none"
                    strokeWidth={14}
                    strokeLinecap="round"
                    className={tone.stroke}
                    strokeDasharray={CIRC}
                    strokeDashoffset={dashoffset}
                    opacity={0.4}
                    style={{
                      filter: "blur(12px)",
                      transition: reduced
                        ? undefined
                        : "stroke-dashoffset 1.5s cubic-bezier(.22,1,.36,1)",
                    }}
                  />
                  <circle
                    cx={CENTRE}
                    cy={CENTRE}
                    r={R}
                    fill="none"
                    strokeWidth={12}
                    strokeLinecap="round"
                    className={tone.stroke}
                    strokeDasharray={CIRC}
                    strokeDashoffset={dashoffset}
                    style={{
                      transition: reduced
                        ? undefined
                        : "stroke-dashoffset 1.5s cubic-bezier(.22,1,.36,1)",
                    }}
                  />
                </g>
              </svg>

              <div
                className="absolute inset-0 flex flex-col items-center justify-center"
                aria-hidden="true"
              >
                <span className="label mb-2">Privacy exposure</span>
                <span className="flex items-baseline gap-1">
                  <span
                    ref={numberRef}
                    className={`mono text-[3.4rem] font-bold leading-none sm:text-[4rem] ${tone.text}`}
                  >
                    {value}
                  </span>
                  <span className="mono text-lg font-medium text-faint">/{score.max}</span>
                </span>
                <span
                  className={`mono mt-3 rounded-pill border px-2.5 py-1 text-[10px]
                              uppercase tracking-[0.16em] ${tone.badge}`}
                >
                  {levelLabel}
                </span>
              </div>
            </div>

            <p className="mt-6 max-w-xs text-center text-sm leading-relaxed text-muted">
              The higher the score, the more exposed your digital identity is.
            </p>
          </div>

          {/* Breakdown */}
          <div className="flex flex-col justify-center">
            <div className="mb-6 flex items-center justify-between gap-4 border-b border-border pb-4">
              <h3 className="label">Exposure breakdown</h3>
              <span className="mono text-[10px] uppercase tracking-[0.16em] text-faint">
                {score.breakdown.length} vectors
              </span>
            </div>

            <div className="flex flex-col gap-5">
              {score.breakdown.map((item, i) => (
                <BreakdownBar
                  key={item.label}
                  item={item}
                  index={i}
                  active={settled}
                  reduced={reduced}
                />
              ))}
            </div>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
              {onViewReport ? (
                <button type="button" className="btn-primary" onClick={onViewReport}>
                  {cta}
                </button>
              ) : (
                <a className="btn-primary" href={reportHref}>
                  {cta}
                </a>
              )}
              <span className="mono text-[11px] text-faint">
                {score.breakdown.filter((b) => b.risk === "high").length} of{" "}
                {score.breakdown.length} vectors rated high
              </span>
            </div>
          </div>
        </div>
      </Reveal>
    </Section>
  );
}

export default ExposureScore;
