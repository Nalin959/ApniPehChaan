import { StatusDot } from "../lib/ui";

/** Footer takes no props — every destination is a real anchor or an href="#". */
export interface FooterProps {
  className?: string;
}

interface FooterLink {
  label: string;
  /** "#" marks a page that does not exist yet; it is still a real anchor. */
  href: string;
}

interface FooterColumn {
  title: string;
  links: FooterLink[];
}

const COLUMNS: FooterColumn[] = [
  {
    title: "Product",
    links: [
      { label: "How It Works", href: "#how-it-works" },
      { label: "Exposure Scan", href: "#exposure-scan" },
      { label: "Privacy Agent", href: "#privacy-agent" },
      { label: "Monitoring", href: "#protection" },
      { label: "Pricing", href: "#pricing" },
    ],
  },
  {
    title: "Privacy",
    links: [
      { label: "Privacy Policy", href: "#" },
      { label: "Security", href: "#" },
      { label: "Data Protection", href: "#" },
      { label: "Terms", href: "#" },
    ],
  },
  {
    title: "Resources",
    links: [
      { label: "Privacy Guide", href: "#" },
      { label: "Data Broker Guide", href: "#" },
      { label: "FAQ", href: "#faq" },
      { label: "Contact", href: "#" },
    ],
  },
];

export default function Footer({ className = "" }: FooterProps) {
  return (
    <footer className={`relative border-t border-border bg-bg ${className}`}>
      {/* A single accent hairline is the only colour up here — it reads as a seam. */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px"
        aria-hidden="true"
        style={{ background: "linear-gradient(90deg, transparent, rgb(var(--accent) / 0.35), transparent)" }}
      />

      <div className="container-x py-14 sm:py-20">
        <div className="grid gap-10 lg:grid-cols-[1fr_1.6fr] lg:gap-16">
          <div className="max-w-sm">
            <p className="text-sm leading-relaxed text-muted">
              Built for people who never agreed to become a data product — and would like
              to stop being one.
            </p>
            <div className="mt-5 inline-flex items-center gap-2 rounded-pill border border-border bg-surface px-3 py-1.5">
              <StatusDot tone="accent" />
              <span className="mono text-[10px] uppercase tracking-[0.16em] text-muted">
                Monitoring active
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-8 sm:grid-cols-3">
            {COLUMNS.map((column) => (
              <nav key={column.title} aria-label={column.title}>
                <h2 className="label mb-4">{column.title}</h2>
                <ul className="space-y-2.5">
                  {column.links.map((link) => (
                    <li key={link.label}>
                      <a
                        href={link.href}
                        className="group inline-flex items-center gap-0 text-sm text-muted transition-colors hover:text-text"
                      >
                        <span
                          aria-hidden="true"
                          className="h-px w-0 bg-accent transition-all duration-300 group-hover:mr-2 group-hover:w-3"
                        />
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </nav>
            ))}
          </div>
        </div>

        <div className="mt-14 flex flex-col gap-6 border-t border-border pt-10 sm:mt-20 sm:flex-row sm:items-end sm:justify-between">
          <div className="mono text-[2rem] font-extrabold leading-[0.88] tracking-tight sm:text-[2.5rem]">
            PRIVACY<span className="text-accent">//</span>
            <br />
            AI
          </div>

          <div className="sm:text-right">
            <p className="text-sm text-muted">Privacy should be a default, not a privilege.</p>
            <p className="mono mt-2 text-[11px] text-faint">© 2026 Privacy//AI</p>
          </div>
        </div>
      </div>
    </footer>
  );
}
