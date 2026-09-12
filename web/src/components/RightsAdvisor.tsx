import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Bot, Minimize2, Send, X } from "lucide-react";
import { sendAdvisorMessage, type ChatMessage } from "../lib/api";
import { usePrefersReducedMotion } from "../lib/hooks";
import { StatusDot } from "../lib/ui";
import type { ScanResult } from "../lib/types";

export interface RightsAdvisorProps {
  result?: ScanResult | null;
}

const DEFAULT_SUGGESTIONS = [
  "What personal data was found?",
  "How does DPDP Act 2023 help me?",
  "How do I remove high risk exposures?",
  "What is an infostealer malware infection?",
];

export default function RightsAdvisor({ result }: RightsAdvisorProps) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "Hello! I am your **SovereignPrivacy Rights Advisor**.\n\nI can analyze your exposures, explain statutory erasure rights (DPDP s.12/s.13, GDPR Art. 17), and help prepare deletion requests. What would you like to review?",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const reduced = usePrefersReducedMotion();

  // Scroll to bottom when messages update
  useEffect(() => {
    if (open && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, open, loading]);

  // Focus input on open
  useEffect(() => {
    if (open && !minimized) {
      inputRef.current?.focus();
    }
  }, [open, minimized]);

  async function handleSend(textToSend?: string) {
    const text = (textToSend || input).trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = { role: "user", content: text };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInput("");
    setLoading(true);

    try {
      const resp = await sendAdvisorMessage(text, nextMessages, {
        tab: "agent",
        risk_score: result?.score.score ?? null,
        exposure_count: result?.counts.total ?? 0,
        email: result?.email ?? "",
      });

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: resp.reply,
          suggested_actions: resp.suggested_actions,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, I had trouble reaching the AI advisor engine. Please check your connection or try again shortly.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    handleSend();
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function formatText(text: string) {
    // Clean, readable basic markdown rendering
    const parts = text.split("\n");
    return parts.map((line, idx) => {
      if (line.startsWith("### ")) {
        return (
          <h4 key={idx} className="mt-2 text-xs font-bold uppercase tracking-wider text-accent">
            {line.replace("### ", "")}
          </h4>
        );
      }
      if (line.startsWith("- ") || line.startsWith("* ")) {
        const item = line.replace(/^[-*]\s+/, "");
        return (
          <li key={idx} className="ml-4 list-disc text-xs leading-relaxed text-text/90">
            {renderBold(item)}
          </li>
        );
      }
      if (!line.trim()) {
        return <div key={idx} className="h-1.5" />;
      }
      return (
        <p key={idx} className="text-xs leading-relaxed text-text/90">
          {renderBold(line)}
        </p>
      );
    });
  }

  function renderBold(str: string) {
    const pieces = str.split(/(\*\*[^*]+\*\*)/g);
    return pieces.map((p, i) => {
      if (p.startsWith("**") && p.endsWith("**")) {
        return (
          <strong key={i} className="font-semibold text-text">
            {p.slice(2, -2)}
          </strong>
        );
      }
      return p;
    });
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
      {/* Floating Trigger Button */}
      {!open && (
        <motion.button
          type="button"
          onClick={() => setOpen(true)}
          initial={reduced ? false : { scale: 0.85, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          className="group flex items-center gap-2.5 rounded-pill border border-border-strong bg-surface/90
                     px-4 py-2.5 shadow-lift backdrop-blur-md transition-all hover:border-accent/40"
          aria-label="Open SovereignPrivacy Rights Advisor"
        >
          <StatusDot tone="accent" live />
          <Bot className="h-4 w-4 text-accent" aria-hidden />
          <span className="mono text-xs font-semibold tracking-wide text-text group-hover:text-accent">
            Rights Advisor
          </span>
          <span className="mono rounded-full bg-accent/15 px-1.5 py-0.5 text-[9px] font-bold text-accent">
            AI
          </span>
        </motion.button>
      )}

      {/* Expanded Chat Dialog */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={reduced ? false : { opacity: 0, y: 16, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={reduced ? { opacity: 0 } : { opacity: 0, y: 16, scale: 0.96 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className={`flex w-[92vw] max-w-[400px] flex-col overflow-hidden rounded-card border
                       border-border bg-surface/95 shadow-lift backdrop-blur-xl transition-all
                       ${minimized ? "h-[54px]" : "h-[540px] max-h-[82vh]"}`}
          >
            {/* Header */}
            <div className="flex shrink-0 items-center justify-between border-b border-border bg-elevated/70 px-4 py-3">
              <div className="flex items-center gap-2.5">
                <StatusDot tone="accent" live={!reduced} />
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="mono text-xs font-bold text-text">Rights Advisor</span>
                    <span className="mono rounded-pill border border-accent/30 bg-accent/10 px-1.5 py-0.2 text-[9px] text-accent">
                      DPDP · GDPR
                    </span>
                  </div>
                  <p className="font-mono text-[9px] text-faint">Grounded in verified exposure findings</p>
                </div>
              </div>

              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setMinimized((m) => !m)}
                  className="rounded p-1 text-faint transition-colors hover:text-text"
                  aria-label={minimized ? "Restore" : "Minimize"}
                >
                  <Minimize2 className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="rounded p-1 text-faint transition-colors hover:text-text"
                  aria-label="Close"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            {/* Chat Body */}
            {!minimized && (
              <>
                <div
                  ref={scrollRef}
                  className="flex-1 space-y-3 overflow-y-auto p-4 [scrollbar-color:rgb(var(--border-strong))_transparent] [scrollbar-width:thin]"
                >
                  {messages.map((m, i) => (
                    <div
                      key={i}
                      className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}
                    >
                      <div
                        className={`max-w-[88%] rounded-card px-3.5 py-2.5 text-xs shadow-sm ${
                          m.role === "user"
                            ? "border border-accent/20 bg-accent/10 text-text"
                            : "border border-border bg-bg/80 text-text"
                        }`}
                      >
                        {formatText(m.content)}
                      </div>

                      {/* Suggested actions if present */}
                      {m.suggested_actions && m.suggested_actions.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {m.suggested_actions.map((act, actIdx) => (
                            <button
                              key={actIdx}
                              type="button"
                              onClick={() => {
                                if (act.action === "scroll_exposures") {
                                  document.getElementById("exposure-scan")?.scrollIntoView({ behavior: "smooth" });
                                } else if (act.action === "scroll_rights") {
                                  document.getElementById("protection")?.scrollIntoView({ behavior: "smooth" });
                                } else {
                                  handleSend(act.label);
                                }
                              }}
                              className="mono rounded-pill border border-border bg-elevated/70 px-2.5 py-1 text-[10px]
                                         text-muted transition-colors hover:border-accent/40 hover:text-accent"
                            >
                              → {act.label}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}

                  {loading && (
                    <div className="flex items-center gap-2 rounded-card border border-border bg-bg/60 px-3.5 py-2.5 text-xs text-muted">
                      <Bot className="h-3.5 w-3.5 animate-spin text-accent" />
                      <span className="mono text-[11px]">Rights Advisor analyzing legal context…</span>
                    </div>
                  )}
                </div>

                {/* Suggestions strip if few messages */}
                {messages.length <= 2 && !loading && (
                  <div className="border-t border-border/50 bg-bg/40 px-3 py-2">
                    <p className="mono mb-1.5 text-[9px] uppercase tracking-wider text-faint">Suggested inquiries</p>
                    <div className="flex flex-wrap gap-1">
                      {DEFAULT_SUGGESTIONS.map((sug) => (
                        <button
                          key={sug}
                          type="button"
                          onClick={() => handleSend(sug)}
                          className="mono rounded border border-border bg-elevated/40 px-2 py-0.5 text-[10px]
                                     text-muted transition-colors hover:border-accent/30 hover:text-text"
                        >
                          {sug}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Input Bar */}
                <form onSubmit={onSubmit} className="border-t border-border bg-elevated/40 p-2.5">
                  <div className="flex items-center gap-2">
                    <input
                      ref={inputRef}
                      type="text"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="Ask about your rights or exposures…"
                      disabled={loading}
                      className="min-w-0 flex-1 rounded-pill border border-border bg-bg/90 px-3.5 py-2 text-xs
                                 text-text placeholder:text-faint focus:border-accent/50 focus:outline-none"
                    />
                    <button
                      type="submit"
                      disabled={!input.trim() || loading}
                      className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent
                                 text-[#04140c] transition-all hover:shadow-glow disabled:opacity-40"
                      aria-label="Send"
                    >
                      <Send className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </form>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
