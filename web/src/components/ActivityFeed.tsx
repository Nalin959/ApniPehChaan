import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Terminal } from "lucide-react";
import { mockActivity } from "../data/mock";
import { usePrefersReducedMotion } from "../lib/hooks";
import { StatusDot } from "../lib/ui";
import type { ActivityEvent, ActivityKind } from "../lib/types";

/** A streamed line keeps its own key: the feed loops, so `event.id` alone repeats. */
interface FeedLine extends ActivityEvent {
  key: string;
}

export interface ActivityFeedProps {
  className?: string;
  /** Height of the scrolling log body in pixels. The header sits above it. */
  height?: number;
  /** Milliseconds between streamed lines. */
  interval?: number;
  /**
   * Upper bound on retained lines. The stream loops forever so the demo never
   * goes dead — without a cap the DOM would grow without limit.
   */
  maxLines?: number;
  events?: ActivityEvent[];
  /** Hides the panel chrome when the feed is embedded inside another card. */
  bare?: boolean;
}

/**
 * Colour carries meaning here, so it is paired with a short textual tag — a
 * screen reader (and anyone who cannot separate the hues) still gets the kind.
 * Class strings are written out in full because Tailwind only ships classes it
 * can see literally in the source.
 */
const KIND_STYLE: Record<ActivityKind, { text: string; tag: string; label: string }> = {
  scan:    { text: "text-info",    tag: "text-info/70",    label: "SCAN" },
  detect:  { text: "text-warning", tag: "text-warning/70", label: "FIND" },
  assess:  { text: "text-danger",  tag: "text-danger/70",  label: "RISK" },
  request: { text: "text-accent",  tag: "text-accent/70",  label: "REQ " },
  monitor: { text: "text-muted",   tag: "text-faint",      label: "WTCH" },
  done:    { text: "text-text",    tag: "text-accent/70",  label: "DONE" },
};

export function ActivityFeed({
  className = "",
  height = 300,
  interval = 900,
  maxLines = 12,
  events = mockActivity,
  bare = false,
}: ActivityFeedProps) {
  const reduced = usePrefersReducedMotion();
  const [lines, setLines] = useState<FeedLine[]>([]);
  const bodyRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (events.length === 0) {
      setLines([]);
      return;
    }

    // Motion is decorative; the log content is the information. With reduced
    // motion the whole list is simply present, no streaming.
    if (reduced) {
      setLines(events.slice(-maxLines).map((e, i) => ({ ...e, key: `${e.id}-static-${i}` })));
      return;
    }

    setLines([]);
    let cursor = 0;
    let pass = 0;
    const id = window.setInterval(() => {
      const event = events[cursor];
      const key = `${event.id}-${pass}`;
      setLines((prev) => {
        const next = [...prev, { ...event, key }];
        return next.length > maxLines ? next.slice(next.length - maxLines) : next;
      });
      cursor += 1;
      if (cursor >= events.length) {
        cursor = 0;
        pass += 1;
      }
    }, interval);

    return () => window.clearInterval(id);
  }, [events, interval, maxLines, reduced]);

  // Pin to the newest line. Assigning scrollTop directly (rather than a smooth
  // scroll) keeps the panel steady when lines arrive close together.
  useEffect(() => {
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines]);

  const shell = bare
    ? "relative overflow-hidden"
    : "card relative overflow-hidden shadow-lift";

  return (
    <div className={`${shell} ${className}`}>
      <header className="flex items-center justify-between gap-3 border-b border-border bg-elevated/60 px-4 py-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <Terminal className="h-3.5 w-3.5 shrink-0 text-accent" aria-hidden="true" />
          <span className="label truncate text-faint">
            Privacy Agent <span className="text-border-strong">/</span>{" "}
            <span className="text-accent">Live</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <StatusDot tone="accent" live={!reduced} />
          <span className="label hidden text-faint sm:inline">Streaming</span>
        </div>
      </header>

      <div className="relative">
        {/* A single sweep of light across the panel — reads as an instrument
            that is powered on. Purely decorative. */}
        {!reduced && (
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-x-0 top-0 z-10 h-16
                       bg-gradient-to-b from-accent/[0.07] to-transparent animate-scan-sweep"
          />
        )}

        <div
          ref={bodyRef}
          style={{ height }}
          className="overflow-y-auto overflow-x-hidden px-4 py-3
                     [scrollbar-color:rgb(var(--border-strong))_transparent] [scrollbar-width:thin]"
        >
          <ul
            role="log"
            aria-live="polite"
            aria-relevant="additions"
            aria-label="Privacy agent activity"
            className="mono space-y-1.5 text-[11px] leading-relaxed sm:text-xs"
          >
            {lines.map((line, i) => {
              const style = KIND_STYLE[line.kind];
              const isLast = i === lines.length - 1;
              const content = (
                <>
                  <span className="text-faint">[{line.time}]</span>{" "}
                  <span className={`${style.tag} hidden sm:inline`} aria-hidden="true">
                    {style.label}
                  </span>{" "}
                  <span className="sr-only">{style.label}: </span>
                  <span className={style.text}>{line.message}</span>
                  {isLast && (
                    <span
                      aria-hidden="true"
                      className={`ml-1 inline-block text-accent ${reduced ? "" : "animate-blink"}`}
                    >
                      &#9611;
                    </span>
                  )}
                </>
              );

              return reduced ? (
                <li key={line.key} className="break-words">{content}</li>
              ) : (
                <motion.li
                  key={line.key}
                  className="break-words"
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
                >
                  {content}
                </motion.li>
              );
            })}
          </ul>
        </div>
      </div>
    </div>
  );
}

export default ActivityFeed;
