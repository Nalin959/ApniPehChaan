import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Menu, X } from "lucide-react";
import { usePrefersReducedMotion, useScrollLock, useScrolled } from "../lib/hooks";

export interface NavLink {
  label: string;
  href: string;
}

export interface NavbarProps {
  /**
   * Fired by the "Start Free Scan" button. When omitted the navbar falls back
   * to focusing the hero's email field, so the control is never a dead end.
   */
  onStartScan?: () => void;
}

/** Single source of truth for the nav — desktop and mobile render the same list. */
const LINKS: NavLink[] = [
  { label: "How It Works", href: "#how-it-works" },
  { label: "Exposure Scan", href: "#exposure-scan" },
  { label: "Privacy Agent", href: "#privacy-agent" },
  { label: "Protection", href: "#protection" },
  { label: "Pricing", href: "#pricing" },
];

const PANEL_ID = "primary-nav-panel";

/** The wordmark is type, not an image — it stays crisp and costs no request. */
function Wordmark() {
  return (
    <a
      href="#top"
      className="group -m-1 shrink-0 rounded p-1"
      aria-label="PRIVACY//AI — home"
    >
      <span
        aria-hidden
        className="block text-[15px] font-extrabold leading-[0.88] tracking-[-0.02em]"
      >
        PRIVACY<span className="text-accent">//</span>
      </span>
      <span
        aria-hidden
        className="block text-[15px] font-extrabold leading-[0.88] tracking-[0.42em] text-muted
                   transition-colors duration-200 group-hover:text-text"
      >
        AI
      </span>
    </a>
  );
}

export default function Navbar({ onStartScan }: NavbarProps) {
  const scrolled = useScrolled(12);
  const reduced = usePrefersReducedMotion();
  const [open, setOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);

  useScrollLock(open);

  const close = useCallback(() => {
    setOpen(false);
    // Returning focus to the toggle keeps keyboard users where they left off.
    toggleRef.current?.focus();
  }, []);

  // Escape closes the panel. Bound only while open so we are not listening on
  // every keystroke for the rest of the session.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close]);

  // A resize into the desktop breakpoint hides the toggle; leaving the panel
  // mounted would trap scroll with no visible way out.
  useEffect(() => {
    if (!open) return;
    const mq = window.matchMedia("(min-width: 768px)");
    const on = () => {
      if (mq.matches) setOpen(false);
    };
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [open]);

  // Move focus into the panel so the next Tab lands on its first link.
  useEffect(() => {
    if (open) panelRef.current?.focus();
  }, [open]);

  const startScan = useCallback(() => {
    setOpen(false);
    if (onStartScan) {
      onStartScan();
      return;
    }
    const field = document.getElementById("hero-email");
    if (field instanceof HTMLInputElement) {
      field.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "center" });
      field.focus({ preventScroll: true });
    }
  }, [onStartScan, reduced]);

  return (
    <header
      className={`sticky top-0 z-50 transition-colors duration-300 ${
        // The open panel is fixed beneath the bar, so a transparent bar would
        // let that content show through it.
        scrolled || open
          ? "border-b border-border bg-bg/70 backdrop-blur-xl"
          : "border-b border-transparent bg-transparent"
      }`}
    >
      <div className="container-x">
        <div className="flex h-16 items-center justify-between gap-4 sm:h-[72px]">
          <Wordmark />

          <nav aria-label="Primary" className="hidden md:block">
            <ul className="flex items-center gap-7 lg:gap-9">
              {LINKS.map((link) => (
                <li key={link.href}>
                  <a
                    href={link.href}
                    className="text-[13px] font-medium text-muted transition-colors duration-200 hover:text-text"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          <div className="hidden items-center gap-2 md:flex">
            <button type="button" onClick={startScan} className="btn-primary !px-4 !py-2 text-[13px]">
              Start Free Scan
              <ArrowRight className="h-3.5 w-3.5" aria-hidden />
            </button>
          </div>

          <button
            ref={toggleRef}
            type="button"
            onClick={() => (open ? close() : setOpen(true))}
            aria-expanded={open}
            aria-controls={PANEL_ID}
            aria-label={open ? "Close menu" : "Open menu"}
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-border
                       text-text transition-colors duration-200 hover:border-border-strong hover:bg-elevated md:hidden"
          >
            {open ? <X className="h-5 w-5" aria-hidden /> : <Menu className="h-5 w-5" aria-hidden />}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            id={PANEL_ID}
            ref={panelRef}
            tabIndex={-1}
            key="panel"
            initial={reduced ? false : { opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduced ? { opacity: 0 } : { opacity: 0, y: -8 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className="fixed inset-x-0 bottom-0 top-16 sm:top-[72px] z-40 overflow-y-auto border-t border-border
                       bg-bg/95 backdrop-blur-xl outline-none md:hidden"
          >
            <nav aria-label="Primary mobile" className="container-x py-8">
              <ul className="flex flex-col">
                {LINKS.map((link, i) => (
                  <motion.li
                    key={link.href}
                    initial={reduced ? false : { opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: reduced ? 0 : 0.04 + i * 0.045, ease: [0.22, 1, 0.36, 1] }}
                    className="border-b border-border"
                  >
                    <a
                      href={link.href}
                      onClick={() => setOpen(false)}
                      className="flex items-center justify-between py-4 text-lg font-semibold tracking-tight
                                 text-text transition-colors duration-200 hover:text-accent"
                    >
                      {link.label}
                      <span className="label text-faint">0{i + 1}</span>
                    </a>
                  </motion.li>
                ))}
              </ul>

              <div className="mt-8">
                <button type="button" onClick={startScan} className="btn-primary w-full">
                  Start Free Scan
                  <ArrowRight className="h-4 w-4" aria-hidden />
                </button>
              </div>

              <p className="mt-8 text-xs leading-relaxed text-faint">
                Your information is never sold. Scans run against public sources only.
              </p>
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
