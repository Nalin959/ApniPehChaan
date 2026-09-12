/**
 * Mock data layer.
 *
 * Every component reads from here rather than holding its own literals, so
 * swapping in a real API later means replacing these functions and nothing
 * else. Source names are deliberately fictional — inventing findings against
 * real companies would be defamatory, and a demo does not need it.
 */
import type {
  ActivityEvent, DataSource, PrivacyScore, RemovalRequest, ScanResult, ScanStep,
} from "../lib/types";

export const mockDataSources: DataSource[] = [
  {
    id: "src-01", name: "Northgate Directory", category: "people-search",
    exposed: ["Name", "Phone", "City"], risk: "high", status: "found",
    discovered: "2 days ago",
    recommendedAction: "Submit an opt-out request",
    detail: "A people-search listing pairs your name with a reachable phone number, which is the combination used for most impersonation attempts.",
  },
  {
    id: "src-02", name: "Vantage Search", category: "people-search",
    exposed: ["Email", "City"], risk: "medium", status: "found",
    discovered: "2 days ago",
    recommendedAction: "Submit an opt-out request",
    detail: "An indexed profile page returns your address on a query for your name.",
  },
  {
    id: "src-03", name: "Meridian Marketing DB", category: "marketing",
    exposed: ["Email", "Age range", "Interests"], risk: "high", status: "analysed",
    discovered: "2 days ago",
    recommendedAction: "Request erasure and withdraw consent",
    detail: "A marketing aggregator holds a behavioural profile assembled without a direct relationship with you.",
  },
  {
    id: "src-04", name: "Orbit Profile", category: "social",
    exposed: ["Name", "Employer"], risk: "low", status: "found",
    discovered: "5 days ago",
    recommendedAction: "Tighten profile visibility",
    detail: "A public profile exposes your employer, which is commonly used to make phishing mail look internal.",
  },
  {
    id: "src-05", name: "Civic Records Index", category: "public-record",
    exposed: ["Address"], risk: "high", status: "removed",
    discovered: "9 days ago",
    recommendedAction: "Removed — monitoring for reappearance",
    detail: "A mirror of a public register. The statutory original cannot be erased; this private copy could be, and was.",
  },
  {
    id: "src-06", name: "Harbor Leak Archive", category: "breach",
    exposed: ["Email", "Password hash"], risk: "high", status: "awaiting",
    discovered: "11 days ago",
    recommendedAction: "Rotate the reused password and enable 2FA",
    detail: "A breach record cannot be un-published. What reduces the harm is making the exposed credential worthless.",
  },
  {
    id: "src-07", name: "Ledger People Finder", category: "data-broker",
    exposed: ["Name", "Phone", "Address"], risk: "medium", status: "requested",
    discovered: "12 days ago",
    recommendedAction: "Awaiting controller response",
    detail: "A broker resells a contact record assembled from several directories.",
  },
  {
    id: "src-08", name: "Beacon Contact Cloud", category: "data-broker",
    exposed: ["Email", "Phone"], risk: "medium", status: "found",
    discovered: "12 days ago",
    recommendedAction: "Submit an opt-out request",
    detail: "A B2B contact database lists a direct line alongside your work address.",
  },
  {
    id: "src-09", name: "Lantern Public Index", category: "directory",
    exposed: ["Name", "City"], risk: "low", status: "found",
    discovered: "14 days ago",
    recommendedAction: "Low priority — monitor",
    detail: "A thin directory entry. Little on its own, but it corroborates richer records elsewhere.",
  },
  {
    id: "src-10", name: "Quarry Data Exchange", category: "data-broker",
    exposed: ["Email", "Employer", "Age range"], risk: "medium", status: "found",
    discovered: "14 days ago",
    recommendedAction: "Submit an opt-out request",
    detail: "An exchange that sells segments to advertisers.",
  },
  {
    id: "src-11", name: "Tidewater Archive", category: "breach",
    exposed: ["Email"], risk: "low", status: "found",
    discovered: "21 days ago",
    recommendedAction: "Confirm the password is not reused",
    detail: "Your address appears in an older credential dump with no password attached.",
  },
  {
    id: "src-12", name: "Summit Registry Mirror", category: "public-record",
    exposed: ["Name", "Address"], risk: "medium", status: "found",
    discovered: "21 days ago",
    recommendedAction: "Request removal of the mirrored copy",
    detail: "A private mirror of a statutory register — the mirror is removable even where the register is not.",
  },
  {
    id: "src-13", name: "Clearpoint Leads", category: "marketing",
    exposed: ["Email", "Phone"], risk: "low", status: "found",
    discovered: "24 days ago",
    recommendedAction: "Withdraw marketing consent",
    detail: "A lead list built from form submissions.",
  },
  {
    id: "src-14", name: "Ashford People Search", category: "people-search",
    exposed: ["Name", "Phone", "Relatives"], risk: "high", status: "found",
    discovered: "26 days ago",
    recommendedAction: "Submit an opt-out request",
    detail: "Listing relatives alongside your contact details is what makes social-engineering attempts convincing.",
  },
];

export const mockPrivacyScore: PrivacyScore = {
  score: 62,
  max: 100,
  level: "High",
  breakdown: [
    { label: "Email exposure", value: 78, risk: "high" },
    { label: "Phone exposure", value: 61, risk: "medium" },
    { label: "Public profile exposure", value: 70, risk: "high" },
    { label: "Data broker exposure", value: 88, risk: "high" },
    { label: "Breach exposure", value: 42, risk: "medium" },
  ],
};

export const mockRemovalRequests: RemovalRequest[] = [
  { id: "req-01", source: "Northgate Directory", type: "Personal Information Removal", stage: "awaiting", submitted: "Today", deadlineDays: 28 },
  { id: "req-02", source: "Meridian Marketing DB", type: "Erasure & Consent Withdrawal", stage: "sent", submitted: "Yesterday", deadlineDays: 27 },
  { id: "req-03", source: "Civic Records Index", type: "Mirrored Record Removal", stage: "removed", submitted: "9 days ago" },
  { id: "req-04", source: "Ledger People Finder", type: "Opt-Out Request", stage: "generated", submitted: "Today", deadlineDays: 30 },
];

export const mockActivity: ActivityEvent[] = [
  { id: "a1", time: "09:41:12", kind: "scan",    message: "Scanning public sources…" },
  { id: "a2", time: "09:41:14", kind: "detect",  message: "New email exposure detected" },
  { id: "a3", time: "09:41:16", kind: "assess",  message: "Risk classification: MEDIUM" },
  { id: "a4", time: "09:41:18", kind: "detect",  message: "Data source identified" },
  { id: "a5", time: "09:41:21", kind: "request", message: "Removal workflow initiated" },
  { id: "a6", time: "09:41:24", kind: "request", message: "Request generated" },
  { id: "a7", time: "09:41:27", kind: "monitor", message: "Monitoring enabled" },
  { id: "a8", time: "09:41:31", kind: "scan",    message: "Cross-checking breach corpora…" },
  { id: "a9", time: "09:41:34", kind: "detect",  message: "Broker listing matched on phone" },
  { id: "a10", time: "09:41:38", kind: "assess", message: "Risk classification: HIGH" },
  { id: "a11", time: "09:41:41", kind: "request",message: "Opt-out request queued for approval" },
  { id: "a12", time: "09:41:45", kind: "done",   message: "Awaiting your approval to send" },
];

export const scanSteps: ScanStep[] = [
  { id: "email",    label: "Email",            duration: 620 },
  { id: "phone",    label: "Phone",            duration: 540 },
  { id: "profiles", label: "Public profiles",  duration: 760 },
  { id: "brokers",  label: "Data brokers",     duration: 900 },
  { id: "breaches", label: "Breach databases", duration: 820 },
  { id: "records",  label: "Public records",   duration: 700 },
];

export const identityFields = [
  "Email", "Phone", "Name", "Address", "Employer",
  "Social profiles", "Public records", "Breached accounts",
] as const;

export const sinkCategories = [
  "Data brokers", "People search", "Marketing databases",
  "Public directories", "Breach databases",
] as const;

/** Shapes a scan result for an address. Deterministic, so the demo repeats. */
export function runMockScan(email: string): ScanResult {
  const sources = mockDataSources;
  const counts = {
    total: sources.length,
    high: sources.filter((s) => s.risk === "high").length,
    medium: sources.filter((s) => s.risk === "medium").length,
    low: sources.filter((s) => s.risk === "low").length,
  };
  return { email, sources, score: mockPrivacyScore, counts };
}

export const riskColor: Record<string, string> = {
  high: "text-danger",
  medium: "text-warning",
  low: "text-accent",
};
export const riskBg: Record<string, string> = {
  high: "bg-danger/10 border-danger/30 text-danger",
  medium: "bg-warning/10 border-warning/30 text-warning",
  low: "bg-accent/10 border-accent/30 text-accent",
};
