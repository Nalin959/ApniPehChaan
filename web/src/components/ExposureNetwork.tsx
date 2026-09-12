/**
 * ExposureNetwork — "your identity has a footprint", shown rather than told.
 *
 * The diagram carries the argument: eight ordinary identity signals at the top,
 * the five classes of place they end up at the bottom, and the observed links
 * between them.
 *
 * Two compositions exist because one cannot serve both ends of the range — a
 * 1000-unit-wide bipartite graph is illegible at 360px, and a stacked list
 * wastes a desktop. Both are decorative (aria-hidden); the single sr-only
 * description list is what assistive technology actually reads, so the
 * accessible content never changes with the breakpoint.
 */
import { identityFields, sinkCategories } from "../data/mock";
import { usePrefersReducedMotion } from "../lib/hooks";
import { Reveal, Section } from "../lib/ui";

export type IdentityField = (typeof identityFields)[number];
export type SinkCategory = (typeof sinkCategories)[number];

export interface ExposureNetworkProps {
  /** Anchor id, so a nav can link straight to the diagram. */
  id?: string;
  className?: string;
}

/**
 * Which signal is known to surface where. Kept here rather than in the mock
 * data layer because it describes this diagram's edges, not the scan result.
 */
const LINKS: Record<IdentityField, readonly SinkCategory[]> = {
  Email: ["Data brokers", "Marketing databases", "Breach databases"],
  Phone: ["Data brokers", "People search", "Marketing databases"],
  Name: ["People search", "Public directories", "Data brokers"],
  Address: ["People search", "Public directories"],
  Employer: ["Marketing databases", "Public directories"],
  "Social profiles": ["People search", "Marketing databases"],
  "Public records": ["Public directories", "People search"],
  "Breached accounts": ["Breach databases", "Data brokers"],
};

/** Two-word labels are split by hand: SVG has no text wrapping. */
const CHIP_LINES: Record<IdentityField, readonly string[]> = {
  Email: ["Email"],
  Phone: ["Phone"],
  Name: ["Name"],
  Address: ["Address"],
  Employer: ["Employer"],
  "Social profiles": ["Social", "profiles"],
  "Public records": ["Public", "records"],
  "Breached accounts": ["Breached", "accounts"],
};

const SINK_TONE: Record<SinkCategory, { fill: string; dot: string; text: string }> = {
  "Data brokers": { fill: "fill-danger", dot: "bg-danger", text: "text-danger" },
  "People search": { fill: "fill-danger", dot: "bg-danger", text: "text-danger" },
  "Marketing databases": { fill: "fill-warning", dot: "bg-warning", text: "text-warning" },
  "Public directories": { fill: "fill-muted", dot: "bg-muted", text: "text-muted" },
  "Breach databases": { fill: "fill-danger", dot: "bg-danger", text: "text-danger" },
};

const EDGES = identityFields.flatMap((field, from) =>
  LINKS[field].map((sink) => ({ from, to: sinkCategories.indexOf(sink) })),
);

/* Wide-canvas geometry. Everything derives from these, so the graph stays
   centred whatever the node counts become. */
const W = 1000;
const H = 560;
const SRC_Y = 28;
const SINK_Y = 486;
const NODE_H = 48;
const srcX = (i: number) => (W / identityFields.length) * (i + 0.5);
const sinkX = (j: number) => (W / sinkCategories.length) * (j + 0.5);

/** Dash period is 12 and the keyframe travels -24, so the loop is seamless. */
const DASH = "4 8";

function WideDiagram({ animate }: { animate: boolean }) {
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMid meet"
      aria-hidden="true"
      focusable="false"
      className="h-auto w-full"
    >
      {/* A held breath of green behind the identity row: this half is you. */}
      <ellipse
        cx={W / 2}
        cy={SRC_Y + NODE_H / 2}
        rx={430}
        ry={44}
        className="fill-accent"
        opacity={0.06}
        style={{ filter: "blur(30px)" }}
      />

      {EDGES.map(({ from, to }) => {
        const x1 = srcX(from);
        const x2 = sinkX(to);
        const d = `M ${x1} ${SRC_Y + NODE_H} C ${x1} 232, ${x2} 322, ${x2} ${SINK_Y}`;
        return (
          <g key={`${from}-${to}`}>
            {/* Solid underlay keeps the structure legible with motion disabled. */}
            <path d={d} className="stroke-border-strong" strokeWidth={1} fill="none" opacity={0.35} />
            <path
              d={d}
              className={`stroke-border-strong ${animate ? "animate-dash-flow" : ""}`}
              strokeWidth={1.25}
              strokeDasharray={DASH}
              fill="none"
              opacity={0.9}
              style={animate ? { animationDelay: `${(from * 0.13 + to * 0.07) * -1}s` } : undefined}
            />
          </g>
        );
      })}

      <line
        x1={40}
        x2={W - 40}
        y1={286}
        y2={286}
        className="stroke-border"
        strokeWidth={1}
        strokeDasharray="2 7"
      />
      <text x={40} y={277} className="fill-faint font-mono" fontSize={9} letterSpacing="1.7">
        COLLECTION SURFACE
      </text>
      <text
        x={W - 40}
        y={277}
        textAnchor="end"
        className="fill-faint font-mono"
        fontSize={9}
        letterSpacing="1.7"
      >
        {EDGES.length} LINKAGES
      </text>

      {identityFields.map((field, i) => {
        const cx = srcX(i);
        const lines = CHIP_LINES[field];
        return (
          <g key={field}>
            <rect
              x={cx - 55}
              y={SRC_Y}
              width={110}
              height={NODE_H}
              rx={9}
              className="fill-elevated stroke-border-strong"
              strokeWidth={1}
            />
            <circle cx={cx - 44} cy={SRC_Y + NODE_H / 2} r={2.5} className="fill-accent" />
            {lines.map((line, k) => (
              <text
                key={line}
                x={cx + 6}
                y={lines.length === 1 ? SRC_Y + 28 : SRC_Y + 21 + k * 14}
                textAnchor="middle"
                className="fill-text font-mono"
                fontSize={11}
              >
                {line}
              </text>
            ))}
          </g>
        );
      })}

      {sinkCategories.map((sink, j) => {
        const cx = sinkX(j);
        const tone = SINK_TONE[sink];
        return (
          <g key={sink}>
            <path
              d={`M ${cx - 5} ${SINK_Y - 10} L ${cx + 5} ${SINK_Y - 10} L ${cx} ${SINK_Y - 2} Z`}
              className="fill-border-strong"
            />
            <rect
              x={cx - 90}
              y={SINK_Y}
              width={180}
              height={NODE_H}
              rx={9}
              className="fill-surface stroke-border-strong"
              strokeWidth={1}
            />
            <circle cx={cx - 72} cy={SINK_Y + NODE_H / 2} r={3} className={tone.fill} />
            <text
              x={cx - 60}
              y={SINK_Y + 28}
              className="fill-text font-mono"
              fontSize={11}
            >
              {sink}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/**
 * Compact connector for the stacked layout. preserveAspectRatio="none" is
 * deliberate here — the box must span whatever width it is given at a fixed
 * height, and non-scaling-stroke keeps the hairlines hairline regardless.
 */
function CompactConnector({ animate }: { animate: boolean }) {
  const top = (i: number) => 16 + (288 / (identityFields.length - 1)) * i;
  const bottom = (j: number) => 32 + (256 / (sinkCategories.length - 1)) * j;
  return (
    <svg
      viewBox="0 0 320 96"
      preserveAspectRatio="none"
      aria-hidden="true"
      focusable="false"
      className="h-24 w-full"
    >
      {EDGES.map(({ from, to }) => {
        const x1 = top(from);
        const x2 = bottom(to);
        const d = `M ${x1} 0 C ${x1} 40, ${x2} 58, ${x2} 96`;
        return (
          <path
            key={`${from}-${to}`}
            d={d}
            fill="none"
            strokeWidth={1}
            vectorEffect="non-scaling-stroke"
            strokeDasharray={DASH}
            className={`stroke-border-strong ${animate ? "animate-dash-flow" : ""}`}
            opacity={0.8}
            style={animate ? { animationDelay: `${(from * 0.13 + to * 0.07) * -1}s` } : undefined}
          />
        );
      })}
    </svg>
  );
}

export function ExposureNetwork({ id = "footprint", className = "" }: ExposureNetworkProps) {
  const reduced = usePrefersReducedMotion();
  const animate = !reduced;

  return (
    <Section
      id={id}
      className={className}
      label="Exposure map"
      title="Your digital identity has a footprint."
      lead="You hand over a few ordinary details. They are copied, joined and resold until a
            stranger can assemble a picture of you that you never agreed to publish."
    >
      <Reveal>
        <div className="card overflow-hidden p-5 sm:p-6 lg:p-8">
          {/* Wide bipartite graph — legible only once there is room for it. */}
          <div className="hidden lg:block">
            <WideDiagram animate={animate} />
          </div>

          {/* Stacked flow for everything narrower. */}
          <div className="lg:hidden" aria-hidden="true">
            <div className="label mb-3">What you share</div>
            <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {identityFields.map((field) => (
                <li
                  key={field}
                  className="flex items-center gap-2 rounded-card border border-border-strong
                             bg-elevated px-2.5 py-1.5"
                >
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                  {/* Wraps rather than truncates: a clipped label is a lost label. */}
                  <span className="mono min-w-0 text-[11px] leading-tight text-text">{field}</span>
                </li>
              ))}
            </ul>

            <CompactConnector animate={animate} />

            <div className="label mb-3">Where it ends up</div>
            <ul className="grid gap-2 sm:grid-cols-2">
              {sinkCategories.map((sink) => {
                const tone = SINK_TONE[sink];
                const count = identityFields.filter((f) => LINKS[f].includes(sink)).length;
                return (
                  <li
                    key={sink}
                    className="flex items-center justify-between gap-3 rounded-card border
                               border-border bg-surface px-3 py-2.5"
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <span className={`h-2 w-2 shrink-0 rounded-full ${tone.dot}`} />
                      <span className="mono truncate text-xs text-text">{sink}</span>
                    </span>
                    <span className={`mono shrink-0 text-[11px] ${tone.text}`}>
                      {count} link{count === 1 ? "" : "s"}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>

          {/* The accessible copy of the diagram, identical at every width. */}
          <div className="sr-only">
            <p>
              Diagram: {identityFields.length} identity signals flow into{" "}
              {sinkCategories.length} categories of data destination, across {EDGES.length}{" "}
              observed linkages.
            </p>
            <dl>
              {identityFields.map((field) => (
                <div key={field}>
                  <dt>{field}</dt>
                  <dd>Appears in: {LINKS[field].join(", ")}.</dd>
                </div>
              ))}
            </dl>
          </div>

          <div
            className="mt-6 grid gap-3 border-t border-border pt-5 sm:grid-cols-3 lg:mt-8"
            aria-hidden="true"
          >
            {[
              { k: "Identity signals", v: identityFields.length },
              { k: "Observed linkages", v: EDGES.length },
              { k: "Destination classes", v: sinkCategories.length },
            ].map((stat) => (
              <div key={stat.k} className="flex items-baseline gap-3">
                <span className="mono text-2xl font-bold text-text">
                  {String(stat.v).padStart(2, "0")}
                </span>
                <span className="label">{stat.k}</span>
              </div>
            ))}
          </div>
        </div>
      </Reveal>
    </Section>
  );
}

export default ExposureNetwork;
