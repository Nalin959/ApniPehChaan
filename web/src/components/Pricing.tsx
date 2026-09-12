import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowRight, Check, CircleCheck, LoaderCircle } from "lucide-react";
import { Pill, Reveal, Section } from "../lib/ui";

/** Pricing takes no props — tiers are fixed content. */
export interface PricingProps {
  className?: string;
}

interface Tier {
  id: string;
  name: string;
  price: string;
  cadence: string;
  blurb: string;
  features: string[];
  featured?: boolean;
}

const TIERS: Tier[] = [
  {
    id: "free",
    name: "Free",
    price: "₹0",
    cadence: "forever",
    blurb: "See exactly what is out there before you decide anything.",
    features: ["Exposure scan", "Privacy score", "Basic monitoring", "Exposure report"],
  },
  {
    id: "pro",
    name: "Pro",
    price: "₹99",
    cadence: "/ month",
    blurb: "The agent does the sending, chasing and re-checking for you.",
    features: [
      "Everything in Free",
      "Automated privacy requests",
      "Continuous monitoring",
      "Removal tracking",
      "Priority alerts",
    ],
    featured: true,
  },
  {
    id: "family",
    name: "Family",
    price: "₹199",
    cadence: "/ month",
    blurb: "One dashboard for the people whose exposure is tied to yours.",
    features: ["Everything in Pro", "Multiple profiles", "Family monitoring", "Central dashboard"],
  },
];

type CtaState = "idle" | "pending" | "done";

/**
 * Demo-only CTA state. There is no payment path in this build, so the button
 * acknowledges the press and settles back rather than pretending to check out.
 */
function useCtaState() {
  const [state, setState] = useState<CtaState>("idle");
  const timers = useRef<number[]>([]);

  useEffect(() => () => {
    timers.current.forEach((id) => window.clearTimeout(id));
    timers.current = [];
  }, []);

  const press = useCallback(() => {
    setState("pending");
    const t = window.setTimeout(() => setState("idle"), 1200);
    timers.current.push(t);

    const el = document.getElementById("hero-email");
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.focus();
    } else {
      document.getElementById("top")?.scrollIntoView({ behavior: "smooth" });
    }
  }, []);

  return { state, press };
}

function TierCard({ tier }: { tier: Tier }) {
  const { state, press } = useCtaState();
  const labelId = `tier-${tier.id}-name`;

  return (
    <article
      aria-labelledby={labelId}
      className={`relative flex h-full flex-col rounded-card border p-6 transition-colors duration-200 sm:p-7 ${
        // The lift lives on the card, not on the Reveal wrapper: framer-motion
        // owns that element's transform and would overwrite a Tailwind translate.
        tier.featured
          ? "border-accent/45 bg-elevated/80 shadow-glow md:-translate-y-4"
          : "card card-hover"
      }`}
    >
      {tier.featured && (
        <span className="absolute -top-3 left-6">
          <Pill className="border-accent/40 bg-bg text-accent shadow-glow-sm">Most popular</Pill>
        </span>
      )}

      <h3 id={labelId} className="mono text-[11px] font-bold uppercase tracking-[0.22em] text-faint">
        {tier.name}
      </h3>

      <div className="mt-4 flex items-baseline gap-1.5">
        <span className="mono text-[2.5rem] font-bold leading-none tracking-tight">{tier.price}</span>
        <span className="mono text-xs text-faint">{tier.cadence}</span>
      </div>

      <p className="mt-3 text-sm leading-relaxed text-muted">{tier.blurb}</p>

      <div className="my-6 h-px w-full bg-border" aria-hidden="true" />

      <ul className="flex-1 space-y-3">
        {tier.features.map((feature, i) => {
          // The first row of Pro/Family is an inheritance line, not a new capability.
          const inherited = i === 0 && feature.startsWith("Everything in");
          return (
            <li key={feature} className="flex items-start gap-2.5">
              <Check
                className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${inherited ? "text-faint" : "text-accent"}`}
                aria-hidden="true"
              />
              <span className={`text-sm leading-snug ${inherited ? "text-faint" : "text-text"}`}>
                {feature}
              </span>
            </li>
          );
        })}
      </ul>

      <button
        type="button"
        onClick={press}
        aria-busy={state === "pending"}
        className={`${tier.featured ? "btn-primary" : "btn-ghost"} mt-7 w-full`}
      >
        {state === "idle" && (<>Start Free <ArrowRight className="h-4 w-4" aria-hidden="true" /></>)}
        {state === "pending" && (<><LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" /> Starting…</>)}
        {state === "done" && (<><CircleCheck className="h-4 w-4" aria-hidden="true" /> Scan queued</>)}
      </button>

      {/* Announce the transient states without moving focus. */}
      <span className="sr-only" aria-live="polite">
        {state === "pending" ? `Starting the ${tier.name} plan` : ""}
        {state === "done" ? `Free scan queued on the ${tier.name} plan` : ""}
      </span>
    </article>
  );
}

export default function Pricing({ className = "" }: PricingProps) {
  return (
    <Section
      id="pricing"
      className={className}
      label="Pricing"
      title="Start free. Upgrade only if you want the work done for you."
      lead="The scan and the score cost nothing — knowing where you stand should not be the paid part."
    >
      {/* pt on the grid leaves room for the raised Pro card's badge. */}
      <div className="grid items-stretch gap-4 pt-4 md:grid-cols-3 md:gap-5">
        {TIERS.map((tier, index) => (
          <Reveal
            key={tier.id}
            delay={index}
            className={tier.featured ? "order-first md:order-none" : ""}
          >
            <TierCard tier={tier} />
          </Reveal>
        ))}
      </div>

      <p className="mt-8 text-center text-xs leading-relaxed text-faint">
        Prices in INR. No card required for the free scan, and you can cancel a paid plan at any time.
        Removal outcomes depend on each source — we handle the request and the follow-up, not the other party's decision.
      </p>
    </Section>
  );
}
