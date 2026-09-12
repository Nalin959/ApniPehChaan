import { useId, useState, type FormEvent } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Lock, ShieldCheck } from "lucide-react";
import ScanConsole from "./ScanConsole";
import { usePrefersReducedMotion } from "../lib/hooks";
import type { ScanResult } from "../lib/types";

export interface HeroProps {
  /** Called with a validated address. The parent owns the scan state machine. */
  onScan: (email: string) => void;
  scanState: "idle" | "running" | "complete";
  result: ScanResult | null;
}

/**
 * Deliberately permissive: this gate exists to catch typos and empty submits,
 * not to adjudicate RFC 5322. Anything stricter rejects real addresses.
 */
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export default function Hero({ onScan, scanState, result }: HeroProps) {
  const reduced = usePrefersReducedMotion();
  const errorId = useId();
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");

  const running = scanState === "running";

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const value = email.trim();
    if (!value) {
      setError("Enter an email address to scan.");
      return;
    }
    if (!EMAIL.test(value)) {
      setError("That does not look like a valid email address.");
      return;
    }
    setError("");
    onScan(value);
  }

  const fade = reduced
    ? {}
    : {
        initial: { opacity: 0, y: 18 },
        animate: { opacity: 1, y: 0 },
      };

  return (
    <section className="relative isolate overflow-hidden pb-16 pt-12 sm:pb-24 sm:pt-20 lg:pb-28 lg:pt-24">
      {/* Background is decorative and clipped by the section, so it can never
          widen the document at narrow viewports. */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <div className="grid-bg mask-fade-b absolute inset-0 opacity-[0.55]" />
        <div
          className="absolute inset-x-0 top-0 h-[70vh]"
          style={{
            background:
              "radial-gradient(58% 52% at 50% -6%, rgb(var(--accent) / 0.13), transparent 68%)",
          }}
        />
        <div
          className="absolute inset-x-0 bottom-0 h-40"
          style={{ background: "linear-gradient(to bottom, transparent, rgb(var(--bg)))" }}
        />
      </div>

      <div className="container-x">
        <div className="grid items-start gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,480px)] lg:gap-14">
          {/* ---- Copy + form ---- */}
          <motion.div {...fade} transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}>
            <div className="mb-7 inline-flex items-center gap-2.5 rounded-pill border border-border bg-surface/60 py-1.5 pl-2 pr-3.5 backdrop-blur-sm">
              <span className="relative inline-flex h-1.5 w-1.5 shrink-0">
                <span className="absolute inline-flex h-full w-full animate-pulse-dot rounded-full bg-accent opacity-70" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
              </span>
              <span className="label text-muted">AI PRIVACY AGENT · LIVE</span>
            </div>

            <h1 className="text-display font-extrabold text-text">
              Your personal data is everywhere.
              <br />
              Take back <span className="text-accent">control.</span>
            </h1>

            <p className="mt-6 max-w-xl text-base leading-relaxed text-muted sm:text-lg">
              Discover where your information is exposed, remove it from unwanted sources, and
              let an AI agent keep watch.
            </p>

            <form onSubmit={handleSubmit} noValidate className="mt-9 max-w-xl">
              <label htmlFor="hero-email" className="sr-only">
                Email address to scan
              </label>

              <div className="flex flex-col gap-2.5 sm:flex-row">
                <input
                  id="hero-email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  inputMode="email"
                  spellCheck={false}
                  placeholder="Enter your email address"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (error) setError("");
                  }}
                  aria-invalid={error ? true : undefined}
                  aria-describedby={error ? errorId : undefined}
                  className={`w-full min-w-0 flex-1 rounded-pill border bg-surface/80 px-5 py-3 text-sm
                              text-text placeholder:text-faint transition-colors duration-200
                              hover:border-border-strong focus:outline-none
                              ${error ? "border-danger/60" : "border-border"}`}
                />
                <button type="submit" disabled={running} className="btn-primary shrink-0 whitespace-nowrap px-6 py-3">
                  {running ? "Scanning…" : "Scan My Digital Footprint"}
                  {!running && <ArrowRight className="h-4 w-4" aria-hidden />}
                </button>
              </div>

              {/* Kept mounted so the message is announced as a change, not as new content. */}
              <div aria-live="polite" className="min-h-[1.25rem]">
                {error && (
                  <p id={errorId} className="pt-2 text-[13px] font-medium text-danger">
                    {error}
                  </p>
                )}
              </div>

              <p className="mt-2 font-mono text-[11px] tracking-[0.04em] text-faint">
                Free scan · Privacy-first · No credit card
              </p>
            </form>

            <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3 border-t border-border pt-6">
              <span className="inline-flex items-center gap-2 text-xs text-muted">
                <ShieldCheck className="h-3.5 w-3.5 text-accent" aria-hidden />
                Your information is never sold.
              </span>
              <span className="inline-flex items-center gap-2 text-xs text-faint">
                <Lock className="h-3.5 w-3.5" aria-hidden />
                Encrypted in transit and at rest
              </span>
            </div>
          </motion.div>

          {/* ---- Console. Below the form on mobile by DOM order. ---- */}
          <motion.div
            {...fade}
            transition={{ duration: 0.6, delay: reduced ? 0 : 0.12, ease: [0.22, 1, 0.36, 1] }}
            className="w-full lg:sticky lg:top-28"
          >
            <ScanConsole state={scanState} result={result} />
          </motion.div>
        </div>
      </div>
    </section>
  );
}
