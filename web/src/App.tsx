import { Suspense, lazy, useCallback, useRef, useState } from "react";
import Navbar from "./components/Navbar";
import Hero from "./components/Hero";
import TrustStats from "./components/TrustStats";
import ScanResults from "./components/ScanResults";
import RightsAdvisor from "./components/RightsAdvisor";
import { executeScan } from "./lib/api";
import { scanSteps } from "./data/mock";
import type { ScanResult } from "./lib/types";
import { usePrefersReducedMotion } from "./lib/hooks";

/**
 * Everything below the fold is code-split. The hero and the scan are what the
 * visitor sees and touches in the first seconds, so those ship in the initial
 * bundle; the rest arrives while they are reading.
 */
const ExposureNetwork  = lazy(() => import("./components/ExposureNetwork"));
const ExposureScore    = lazy(() => import("./components/ExposureScore"));
const HowItWorks       = lazy(() => import("./components/HowItWorks"));
const SourceExplorer   = lazy(() => import("./components/SourceExplorer"));
const RemovalFlow      = lazy(() => import("./components/RemovalFlow"));
const PrivacyAgent     = lazy(() => import("./components/PrivacyAgent"));
const PrivacyRights    = lazy(() => import("./components/PrivacyRights"));
const BeforeAfter      = lazy(() => import("./components/BeforeAfter"));
const DashboardPreview = lazy(() => import("./components/DashboardPreview"));
const Features         = lazy(() => import("./components/Features"));
const Pricing          = lazy(() => import("./components/Pricing"));
const FAQ              = lazy(() => import("./components/FAQ"));
const FinalCTA         = lazy(() => import("./components/FinalCTA"));
const Footer           = lazy(() => import("./components/Footer"));

export type ScanState = "idle" | "running" | "complete";

/** Total time the staged scan animation takes, derived from the step table. */
const SCAN_MS = scanSteps.reduce((total, step) => total + step.duration, 0);

export default function App() {
  const [scanState, setScanState] = useState<ScanState>("idle");
  const [result, setResult] = useState<ScanResult | null>(null);
  const timer = useRef<number | null>(null);
  const reduced = usePrefersReducedMotion();

  const handleScan = useCallback(async (email: string) => {
    if (timer.current) window.clearTimeout(timer.current);
    setScanState("running");

    // Trigger real backend scan in parallel with the staged scanning visualization
    const scanPromise = executeScan(email);

    const settle = async () => {
      const next = await scanPromise;
      setResult(next);
      setScanState("complete");
      // Bring the payoff into view rather than leaving it below the fold.
      window.requestAnimationFrame(() => {
        document.getElementById("scan-results")
          ?.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
      });
    };

    if (reduced) {
      await settle();
    } else {
      timer.current = window.setTimeout(settle, SCAN_MS + 500);
    }
  }, [reduced]);

  const restart = useCallback(() => {
    if (timer.current) window.clearTimeout(timer.current);
    setScanState("idle");
    setResult(null);
    document.getElementById("top")?.scrollIntoView({ behavior: reduced ? "auto" : "smooth" });
  }, [reduced]);

  return (
    <>
      {/* Keyboard users land here first and can jump the navigation. */}
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4
                                focus:z-[100] focus:rounded-pill focus:bg-accent focus:px-4
                                focus:py-2 focus:text-sm focus:font-semibold focus:text-[#04140c]">
        Skip to content
      </a>

      <Navbar onStartScan={restart} />

      <main id="main">
        <div id="top" />
        <Hero onScan={handleScan} scanState={scanState} result={result} />
        <TrustStats result={result} />

        {scanState === "complete" && result && (
          <div id="scan-results" className="scroll-mt-24">
            <ScanResults result={result} onRescan={restart} />
          </div>
        )}

        <Suspense fallback={<div className="h-32" aria-hidden="true" />}>
          <ExposureNetwork />
          <ExposureScore score={result?.score} />
          <HowItWorks />
          <SourceExplorer sources={result?.sources} />
          <RemovalFlow />
          <PrivacyAgent />
          <BeforeAfter />
          <DashboardPreview />
          <Features />
          <PrivacyRights />
          <Pricing />
          <FAQ />
          <FinalCTA onStartScan={restart} />
          <Footer />
        </Suspense>
      </main>

      {/* Sitewide AI Rights Advisor connected to Groq/Gemini /api/agent/chat */}
      <RightsAdvisor result={result} />
    </>
  );
}
