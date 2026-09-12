import { ArrowRight, BellOff, Eye, PencilLine, Trash2 } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Reveal, Section } from "../lib/ui";

interface Right {
  id: string;
  title: string;
  copy: string;
  /**
   * Names the term the right is commonly known by. Deliberately descriptive —
   * naming a concept is safe, naming a statute as a guarantee is not.
   */
  note: string;
  Icon: LucideIcon;
}

const RIGHTS: Right[] = [
  {
    id: "access",
    title: "Access",
    copy: "See what information an organisation holds.",
    note: "Often called a subject access or “right to know” request.",
    Icon: Eye,
  },
  {
    id: "correct",
    title: "Correct",
    copy: "Request inaccurate information to be updated.",
    note: "Sometimes called rectification.",
    Icon: PencilLine,
  },
  {
    id: "delete",
    title: "Delete",
    copy: "Request deletion where applicable.",
    note: "Sometimes called erasure. Some records cannot lawfully be deleted.",
    Icon: Trash2,
  },
  {
    id: "withdraw",
    title: "Withdraw",
    copy: "Withdraw consent where applicable.",
    note: "Relevant where processing relies on consent you previously gave.",
    Icon: BellOff,
  },
];

export interface PrivacyRightsProps {
  id?: string;
  className?: string;
  /** Target for the "Understand your rights" link. */
  learnMoreHref?: string;
}

export function PrivacyRights({
  id = "protection",
  className = "",
  learnMoreHref = "#privacy-agent",
}: PrivacyRightsProps) {
  return (
    <Section
      id={id}
      className={className}
      label="Your rights"
      title="Know your privacy rights."
      lead="Depending on where you live and who holds your information, you may be able to ask an organisation to do the following. Knowing the vocabulary is most of the work."
    >
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {RIGHTS.map((r, i) => (
          <Reveal as="li" key={r.id} delay={i} className="h-full">
            <article className="card card-hover group flex h-full flex-col p-5 sm:p-6">
              <div className="flex items-start justify-between gap-3">
                <span
                  className="flex h-9 w-9 items-center justify-center rounded-full border border-border
                             bg-elevated text-muted transition-colors duration-200
                             group-hover:border-accent/40 group-hover:text-accent"
                >
                  <r.Icon className="h-4 w-4" strokeWidth={1.9} aria-hidden="true" />
                </span>
                <span className="mono text-[10px] text-faint">
                  {String(i + 1).padStart(2, "0")}
                </span>
              </div>

              <h3 className="mono mt-5 text-xs font-bold uppercase tracking-[0.18em] text-text">
                {r.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{r.copy}</p>
              <p className="mt-auto pt-4 text-[11px] leading-relaxed text-faint">{r.note}</p>
            </article>
          </Reveal>
        ))}
      </ul>

      <Reveal delay={4} className="mt-8">
        <div className="card flex flex-col gap-5 p-5 sm:p-6 md:flex-row md:items-center md:justify-between">
          {/* The hedging here is load-bearing. Rights differ by jurisdiction, by
              organisation and by record type, and some requests can lawfully be
              refused — promising an outcome would be both wrong and unkind. */}
          <p className="max-w-2xl text-[13px] leading-relaxed text-muted">
            <span className="label mb-2 block">Please note</span>
            These are general descriptions, not legal advice. Which rights are available to you,
            how they apply and how an organisation must respond depend on your jurisdiction, the
            organisation involved and the type of information held — and some requests can lawfully
            be refused or limited. We help you ask clearly and keep track of the answer; we cannot
            promise a particular outcome.
          </p>

          <a
            href={learnMoreHref}
            className="btn-ghost shrink-0 self-start md:self-auto"
          >
            Understand your rights
            <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </a>
        </div>
      </Reveal>
    </Section>
  );
}

export default PrivacyRights;
