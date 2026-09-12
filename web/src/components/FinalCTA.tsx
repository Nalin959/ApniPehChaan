import { useMemo } from "react";
import type { CSSProperties, MouseEvent } from "react";
import { ArrowRight } from "lucide-react";
import { Reveal } from "../lib/ui";
import { usePrefersReducedMotion } from "../lib/hooks";

export interface FinalCTAProps {
  /** Sends the visitor back to the hero scan. Falls back to the #top anchor. */
  onStartScan?: () => void;
  className?: string;
}

interface FieldNode {
  x: number;
  y: number;
  r: number;
  delay: number;
  duration: number;
}

interface FieldEdge {
  a: FieldNode;
  b: FieldNode;
  delay: number;
}

const VIEW_W = 1200;
const VIEW_H = 560;
const NODE_COUNT = 34;

/** Deterministic PRNG so the field is identical on every render and reload. */
function mulberry32(seed: number) {
  let t = seed;
  return () => {
    t |= 0;
    t = (t + 0x6d2b79f5) | 0;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

function buildField(): { nodes: FieldNode[]; edges: FieldEdge[] } {
  const rand = mulberry32(20260913);
  const nodes: FieldNode[] = Array.from({ length: NODE_COUNT }, () => ({
    x: rand() * VIEW_W,
    y: rand() * VIEW_H,
    r: 1.4 + rand() * 2.4,
    delay: rand() * 6,
    duration: 4.5 + rand() * 5.5,
  }));

  // Join each node to its nearest neighbour that is close enough to read as a
  // link. Plain loops over 34 points, run once and memoised — there is no
  // per-frame work anywhere in this background.
  const edges: FieldEdge[] = [];
  for (let i = 0; i < nodes.length; i += 1) {
    const a = nodes[i];
    let bestIndex = -1;
    let bestDistance = Infinity;
    for (let j = 0; j < nodes.length; j += 1) {
      if (i === j) continue;
      const distance = Math.hypot(a.x - nodes[j].x, a.y - nodes[j].y);
      if (distance < bestDistance) { bestDistance = distance; bestIndex = j; }
    }
    if (bestIndex >= 0 && bestDistance < 210) {
      edges.push({ a, b: nodes[bestIndex], delay: (i % 7) * 0.6 });
    }
  }

  return { nodes, edges };
}

/**
 * The background network. Entirely CSS-driven: every node and link reuses the
 * project's existing keyframes with an inline delay, so there is no rAF loop
 * and no scroll listener behind this section.
 */
function DataField() {
  const { nodes, edges } = useMemo(buildField, []);

  return (
    <svg
      className="pointer-events-none absolute inset-0 h-full w-full"
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
    >
      <g stroke="rgb(var(--accent))" strokeWidth="1">
        {edges.map((edge, i) => (
          <line
            key={`e${i}`}
            x1={edge.a.x} y1={edge.a.y} x2={edge.b.x} y2={edge.b.y}
            strokeDasharray="3 9"
            className="animate-dash-flow"
            style={{ opacity: 0.16, animationDelay: `${edge.delay}s` } as CSSProperties}
          />
        ))}
      </g>
      <g fill="rgb(var(--accent))">
        {nodes.map((node, i) => (
          <circle
            key={`n${i}`}
            cx={node.x} cy={node.y} r={node.r}
            className="animate-pulse-dot"
            style={{
              opacity: 0.45,
              animationDelay: `${node.delay}s`,
              animationDuration: `${node.duration}s`,
            } as CSSProperties}
          />
        ))}
      </g>
    </svg>
  );
}

export default function FinalCTA({ onStartScan, className = "" }: FinalCTAProps) {
  const reduced = usePrefersReducedMotion();

  const handleStart = (event: MouseEvent<HTMLAnchorElement>) => {
    // Without the prop the anchor still works — the handler is an enhancement.
    if (!onStartScan) return;
    event.preventDefault();
    onStartScan();
  };

  return (
    <section
      id="start"
      className={`relative overflow-hidden border-y border-border py-24 sm:py-32 ${className}`}
    >
      <div className="grid-bg mask-fade-b pointer-events-none absolute inset-0 opacity-50" aria-hidden="true" />
      {/* The animated field is decorative only, so reduced motion drops it entirely. */}
      {!reduced && <DataField />}
      <div
        className="pointer-events-none absolute inset-0"
        aria-hidden="true"
        style={{
          background:
            "radial-gradient(58% 48% at 50% 42%, rgb(var(--accent) / 0.10), transparent 72%)",
        }}
      />

      <div className="container-x relative">
        <div className="mx-auto max-w-3xl text-center">
          <Reveal>
            <h2 className="text-display font-extrabold">
              Your data<br className="sm:hidden" /> belongs to you.
            </h2>
          </Reveal>

          <Reveal delay={1}>
            <p className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-muted sm:text-lg">
              Find it. Understand it. Remove it. Keep watching.
            </p>
          </Reveal>

          <Reveal delay={2}>
            <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <a
                href="#top"
                onClick={handleStart}
                className="btn-primary w-full px-7 py-3 text-[15px] sm:w-auto"
              >
                Start My Free Scan
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </a>
              <a href="#how-it-works" className="btn-ghost w-full px-7 py-3 text-[15px] sm:w-auto">
                Explore the Platform
              </a>
            </div>
          </Reveal>

          <Reveal delay={3}>
            <p className="mono mt-8 text-[11px] uppercase tracking-[0.16em] text-faint">
              No card required · About 40 seconds · Delete your account any time
            </p>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
