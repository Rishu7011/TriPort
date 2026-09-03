/**
 * TriPort API Types & Interfaces
 * Matches backend schemas in docs/api-contracts.md, orchestrator, and microservices.
 */

export type Role = "officer" | "supervisor" | "auditor" | "admin";

export interface UserProfileResponse {
  user_id: string;
  email: string;
  role: Role;
  name?: string;
  badge_number: string;
  checkpoint_id: string;
  permissions: string[];
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserProfileResponse;
}

export type DocumentType =
  | "passport"
  | "visa"
  /** Aadhaar cards are processed by the backend's national-ID workflow. */
  | "national_id"
  | "pan_card"
  | "voter_id"
  | "driving_license"
  | "permit"
  | "ferry_ticket";

export type CheckpointType = "airport" | "land_border" | "sea";

export type RiskBand = "low" | "medium" | "high" | "critical";

export interface ExtractedFieldItem {
  field_name: string;
  field_value: string | null;
  confidence: number | null;
}

export interface MrzFields {
  doc_number?: string;
  dob?: string;
  expiry?: string;
  nationality?: string;
  sex?: string;
  surname?: string;
  given_names?: string;
  [key: string]: string | undefined;
}

export interface MrzResult {
  mrz_present: boolean;
  checksum_valid: boolean | null;
  checksum_failures: string[];
  mrz_fields: MrzFields;
}

export interface ExtractionResult {
  document_type: DocumentType | string;
  fields: ExtractedFieldItem[];
  mrz?: MrzResult;
  uploaded_at?: string;
  image_url?: string;
}

export interface RuleResultItem {
  rule_name: string;
  passed: boolean;
  detail: string;
  severity?: "critical" | "high" | "medium" | "low" | string;
}

export interface ValidationResult {
  document_type: DocumentType | string;
  passed: boolean;
  failed_rules: string[];
  rule_results: RuleResultItem[];
}

export interface TamperingCheckItem {
  check_type: string;
  score: number;
  flagged: boolean;
  /**
   * The tampering service returns a human-readable string, but persisted
   * legacy checks can contain structured forensic metadata.
   */
  detail: unknown;
}

export interface TamperingResult {
  flagged: boolean;
  tampering_score: number;
  checks: TamperingCheckItem[];
  ela_heatmap_base64?: string;
  image_url?: string;
}

export interface FaceOneToOneResult {
  matched: boolean;
  match_score: number;
  cosine_similarity: number;
  threshold: number;
  detail: string;
}

export interface FaceDedupHit {
  document_id: string;
  similarity: number;
}

export interface FaceDedupResult {
  has_duplicates: boolean;
  hits: FaceDedupHit[];
  person_cluster_id: string | null;
}

export interface FaceVerificationResult {
  one_to_one?: FaceOneToOneResult;
  dedup?: FaceDedupResult;
  has_face_record?: boolean;
  person_cluster_id?: string | null;
  bypassed?: boolean;
  bypassed_reason?: string | null;
}

export interface RiskSubScores {
  validation_score: number;
  tampering_score: number;
  face_match_score: number;
  blacklist_score: number;
  [key: string]: number;
}

export interface RiskScoreResponse {
  score: number;
  band: RiskBand;
  reasons: string[];
  sub_scores?: RiskSubScores;
  computed_at?: string;
}

export interface ServiceStatusMap {
  [serviceName: string]: {
    available: boolean;
  };
}

export interface PipelineResult {
  document_id: string;
  degraded: boolean;
  service_statuses: ServiceStatusMap;
  extraction: ExtractionResult | null;
  validation: ValidationResult | null;
  tampering: TamperingResult | null;
  face: FaceVerificationResult | null;
  risk_score: RiskScoreResponse | null;
}

export interface UploadResponse {
  document_id: string;
  status: "complete" | "degraded" | "pending_biometric" | string;
  pipeline: PipelineResult;
  doc_image_url?: string;
  doc_face_crop_url?: string;
  live_image_url?: string;
  inspection_status?: string;
}

/** Values accepted by POST /documents/{id}/decision. */
export type DecisionVerdict = "approve" | "flag" | "reject";

export interface DecisionRequest {
  officer_id?: string;
  decision: DecisionVerdict | string;
  notes?: string;
}

export interface DecisionResponse {
  document_id: string;
  decision: string;
  recorded: boolean;
  ledger_sequence: number | null;
}

export interface AuditLedgerEvent {
  sequence_num: number;
  event_type: string;
  payload_hash: string;
  prev_record_hash: string;
  record_hash: string;
  officer_id: string | null;
  created_at: string;
}

export interface AuditTrailResponse {
  document_id: string;
  event_count: number;
  events: AuditLedgerEvent[];
}

export interface ChainVerificationResponse {
  valid: boolean;
  total_events: number;
  first_invalid_sequence: number | null;
  detail: string;
}

export interface SummaryStats {
  total_scans: number;
  risk_distribution: Record<string, number>;
  checkpoint_distribution: Record<string, number>;
  flagged_today: number;
  critical_count: number;
  high_count: number;
}

export interface RecentScan {
  document_id: string;
  document_type: string;
  checkpoint_id: string | null;
  uploaded_at: string | null;
  risk_score: number | null;
  risk_band: RiskBand | string | null;
  reasons: string[];
}

export interface BlacklistEntryOut {
  id: string;
  document_number: string | null;
  full_name: string | null;
  date_of_birth: string | null;
  nationality: string | null;
  severity: "watch" | "caution" | "detain" | string;
  reason: string | null;
  created_at: string | null;
}

export interface BlacklistEntryIn {
  document_number?: string | null;
  full_name?: string | null;
  date_of_birth?: string | null;
  nationality?: string | null;
  severity?: string;
  reason?: string | null;
}

export interface ClusterDocument {
  document_id: string;
  checkpoint_type?: string | null;
  checkpoint_id?: string | null;
  checkpoint_name?: string | null;
  uploaded_at?: string | null;
  document_type?: string | null;
  name?: string | null;
  document_number?: string | null;
  nationality?: string | null;
  date_of_birth?: string | null;
  risk_score?: number | null;
  risk_band?: RiskBand | string | null;
  similarity?: number | null;
}

export interface CrossCheckpointFlag {
  flag_type: string;
  severity: string;
  detail: string;
  related_document_ids?: string[];
  timestamp?: string | null;
}

export interface ClusterHistoryResponse {
  person_cluster_id: string;
  total_documents: number;
  documents: ClusterDocument[];
  flags: CrossCheckpointFlag[];
  cross_checkpoint_risk: number;
  repeat_offender_hit: boolean;
  highest_prior_risk_band: string | null;
  highest_prior_risk_score: number | null;
  recommended_escalation: boolean;
  summary: string;
}

export interface ValidationRuleItem {
  rule_name: string;
  description: string;
  rule_type: "date_check" | "regex_format" | "cross_field" | "checksum";
  field: string;
  condition?: string;
  pattern?: string;
  error_message: string;
  document_type: DocumentType | string;
  active?: boolean;
}

export interface FraudClusterNode {
  id: string;
  label: string;
  type: "person" | "document" | "checkpoint";
  riskBand?: RiskBand;
  clusterId?: string;
  details?: Record<string, unknown>;
  x?: number;
  y?: number;
}

export interface FraudClusterLink {
  source: string;
  target: string;
  label: string;
  flagType?: string;
  severity?: "low" | "medium" | "high" | "critical";
}

export interface FraudGraphData {
  nodes: FraudClusterNode[];
  links: FraudClusterLink[];
  clusters: Array<{
    cluster_id: string;
    primary_name: string;
    total_identities: number;
    risk_score: number;
    risk_band: RiskBand;
    flags_count: number;
  }>;
}
