/** Shared shapes. The mock layer and any future API must both satisfy these. */

export type RiskLevel = "high" | "medium" | "low";

export type SourceStatus =
  | "found"
  | "analysed"
  | "requested"
  | "awaiting"
  | "removed";

export type SourceCategory =
  | "data-broker"
  | "people-search"
  | "marketing"
  | "directory"
  | "breach"
  | "public-record"
  | "social";

export interface DataSource {
  id: string;
  name: string;
  category: SourceCategory;
  /** Field names exposed, e.g. ["Name", "Phone"]. */
  exposed: string[];
  risk: RiskLevel;
  status: SourceStatus;
  discovered: string;
  recommendedAction: string;
  /** Plain-language note on why this matters. */
  detail: string;
}

export interface ExposureBreakdownItem {
  label: string;
  /** 0-100. */
  value: number;
  risk: RiskLevel;
}

export interface PrivacyScore {
  score: number;
  max: number;
  level: "Low" | "Moderate" | "High" | "Critical";
  breakdown: ExposureBreakdownItem[];
}

export type RequestStage =
  | "found"
  | "analysed"
  | "generated"
  | "sent"
  | "awaiting"
  | "removed";

export interface RemovalRequest {
  id: string;
  source: string;
  type: string;
  stage: RequestStage;
  submitted: string;
  /** Days until the controller's statutory deadline, when one applies. */
  deadlineDays?: number;
}

export type ActivityKind = "scan" | "detect" | "assess" | "request" | "monitor" | "done";

export interface ActivityEvent {
  id: string;
  time: string;
  kind: ActivityKind;
  message: string;
}

export interface ScanStep {
  id: string;
  label: string;
  /** Milliseconds this step appears to take during the demo scan. */
  duration: number;
}

export interface ScanResult {
  email: string;
  sources: DataSource[];
  score: PrivacyScore;
  counts: { total: number; high: number; medium: number; low: number };
}
