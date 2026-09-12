import { useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { Reveal, Section } from "../lib/ui";
import { usePrefersReducedMotion } from "../lib/hooks";

/** FAQ takes no props — the question set is fixed content. */
export interface FAQProps {
  className?: string;
}

interface QA {
  id: string;
  question: string;
  answer: string;
}

/**
 * Answers are deliberately conservative. A privacy product that over-promises
 * on legal outcomes or security certifications is the exact thing it claims to
 * protect people from, so the wording says what we do and where the limits are.
 */
const ITEMS: QA[] = [
  {
    id: "how-scan-works",
    question: "How does the exposure scan work?",
    answer:
      "You give us one identifier — usually an email address — and we query public sources, people-search sites, data-broker listings and known breach corpora for records that match it. Every hit is scored on how confidently it points at you and how much harm the exposed combination enables. A scan only reads: nothing is submitted, changed or removed until you approve it.",
  },
  {
    id: "what-we-search",
    question: "What information do you search for?",
    answer:
      "The identifiers you give us, plus the fields that are commonly published next to them: name, email, phone, city or address, employer, public profiles and breached credentials. We do not go looking for sensitive categories you have not asked us about, and you can narrow or widen the list at any point.",
  },
  {
    id: "do-you-store",
    question: "Do you store my personal information?",
    answer:
      "We store what is needed to run your scans and send requests on your behalf — the identifiers you provided, the findings, and the history of what was sent and when. You can export that record or delete your account, which deletes it. We do not sell your data or pass it to advertisers.",
  },
  {
    id: "diy",
    question: "Can I remove my information myself?",
    answer:
      "Yes, and you should be able to. Every source we surface comes with its opt-out route and the contact we would write to, whether or not you are paying. The paid plans exist because doing this by hand means tracking dozens of forms, formats and deadlines — not because the route is a secret.",
  },
  {
    id: "requests",
    question: "How are removal requests handled?",
    answer:
      "Each request is drafted against the ground that actually applies to that source, sent to its published privacy contact, and logged with the date the response window starts. Replies are recorded against the request, and when a source says it has removed a listing we re-check the listing rather than take their word for it.",
  },
  {
    id: "refusal",
    question: "What happens if a company refuses to remove my data?",
    answer:
      "A company can refuse, and sometimes the refusal is legitimate — a statutory register or an ongoing legal obligation can override a deletion request. We record the reason given, and where it looks unfounded we help you escalate: a follow-up that addresses the specific ground, and if it comes to it, a complaint to the relevant data-protection authority. We cannot promise an outcome, only that the request is properly made and properly pursued.",
  },
  {
    id: "frequency",
    question: "How frequently is my information monitored?",
    answer:
      "Free accounts get a periodic re-scan. Paid plans run a continuous cycle — a full sweep roughly every 30 days, plus targeted checks when a new breach corpus appears or a source you have an open request with changes. Anything that reappears after removal re-opens the case and alerts you.",
  },
  {
    id: "encryption",
    question: "Is my information encrypted?",
    answer:
      "Yes. Data is encrypted in transit with TLS and encrypted at rest, and internal access is limited to the systems that need it to run your scans and requests. We are not going to claim a certification we have not been audited for — if you need our current security documentation for a review, ask and we will send what we actually hold.",
  },
];

export default function FAQ({ className = "" }: FAQProps) {
  const [openId, setOpenId] = useState<string | null>(ITEMS[0].id);
  const reduced = usePrefersReducedMotion();
  const headerRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const onHeaderKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const moves: Record<string, number> = {
      ArrowDown: index + 1,
      ArrowUp: index - 1,
      Home: 0,
      End: ITEMS.length - 1,
    };
    const target = moves[event.key];
    if (target === undefined) return;
    event.preventDefault();
    headerRefs.current[(target + ITEMS.length) % ITEMS.length]?.focus();
  };

  return (
    <Section
      id="faq"
      className={className}
      label="Questions"
      title="The things people ask before they trust us with an email address."
      lead="Short, specific answers — including the ones where the honest answer is “it depends”."
    >
      <div className="max-w-3xl">
        <ul className="divide-y divide-border border-y border-border">
          {ITEMS.map((item, index) => {
            const open = openId === item.id;
            const buttonId = `faq-trigger-${item.id}`;
            const panelId = `faq-panel-${item.id}`;
            return (
              <li key={item.id}>
                <h3>
                  <button
                    ref={(el) => { headerRefs.current[index] = el; }}
                    type="button"
                    id={buttonId}
                    aria-expanded={open}
                    aria-controls={panelId}
                    onClick={() => setOpenId(open ? null : item.id)}
                    onKeyDown={(e) => onHeaderKeyDown(e, index)}
                    className="group flex w-full items-center gap-4 py-5 text-left transition-colors hover:text-accent"
                  >
                    <span className={`mono shrink-0 text-[11px] tracking-[0.18em] transition-colors ${open ? "text-accent" : "text-faint"}`}>
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="flex-1 text-[15px] font-semibold tracking-tight sm:text-base">
                      {item.question}
                    </span>
                    <ChevronDown
                      aria-hidden="true"
                      className={`h-4 w-4 shrink-0 transition-transform duration-300 ${
                        open ? "rotate-180 text-accent" : "text-faint group-hover:text-muted"
                      }`}
                    />
                  </button>
                </h3>

                {/* The region stays mounted so aria-controls always resolves; the
                    answer itself mounts and unmounts so collapsed text is never
                    read out or reachable. */}
                <div id={panelId} role="region" aria-labelledby={buttonId}>
                  <AnimatePresence initial={false}>
                    {open && (
                      <motion.div
                        key="content"
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={
                          reduced
                            ? { duration: 0 }
                            : { height: { duration: 0.32, ease: [0.22, 1, 0.36, 1] }, opacity: { duration: 0.22 } }
                        }
                        style={{ overflow: "hidden" }}
                      >
                        <p className="max-w-prose pb-6 pl-[2.1rem] pr-2 text-sm leading-relaxed text-muted">
                          {item.answer}
                        </p>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </li>
            );
          })}
        </ul>

        <Reveal className="mt-8">
          <p className="text-sm text-muted">
            Still unsure?{" "}
            <a href="#top" className="font-medium text-accent underline-offset-4 hover:underline">
              Run the free scan
            </a>{" "}
            — it answers most of this with your own data, and costs nothing to find out.
          </p>
        </Reveal>
      </div>
    </Section>
  );
}
