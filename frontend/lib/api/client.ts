import type {
  LoginRequest,
  LoginResponse,
  UserProfileResponse,
  UploadResponse,
  DecisionRequest,
  DecisionResponse,
  AuditTrailResponse,
  ChainVerificationResponse,
  SummaryStats,
  RecentScan,
  BlacklistEntryOut,
  BlacklistEntryIn,
  ExtractionResult,
  ValidationResult,
  TamperingResult,
  FaceVerificationResult,
  RiskScoreResponse,
  ClusterHistoryResponse,
} from "./types";

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8007";

export function getStoredToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)triport_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export function setStoredToken(token: string | null) {
  if (typeof document === "undefined") return;
  if (token) {
    document.cookie = `triport_token=${encodeURIComponent(
      token
    )}; path=/; max-age=604800; SameSite=Lax`;
  } else {
    document.cookie =
      "triport_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax";
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = new Headers(options.headers || {});

  const token = getStoredToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  // If body is not FormData, default to application/json
  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorData: Record<string, unknown> = {};
    try {
      errorData = (await response.json()) as Record<string, unknown>;
    } catch {
      errorData = { detail: response.statusText };
    }
    const detailObj = typeof errorData?.detail === "object" && errorData?.detail !== null
      ? (errorData.detail as Record<string, unknown>)
      : null;

    const message =
      detailObj?.reason ||
      detailObj?.error ||
      errorData?.detail ||
      errorData?.message ||
      `HTTP ${response.status} ${response.statusText}`;
    throw new ApiError(
      typeof message === "string" ? message : JSON.stringify(message),
      response.status,
      errorData
    );
  }

  // Check if 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  // Auth
  login: (credentials: LoginRequest): Promise<LoginResponse> =>
    request<LoginResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    }),

  getMe: (): Promise<UserProfileResponse> =>
    request<UserProfileResponse>("/api/v1/auth/me"),

  // Screening & Documents
  uploadDocument: (formData: FormData): Promise<UploadResponse> =>
    request<UploadResponse>("/api/v1/documents/upload", {
      method: "POST",
      body: formData,
    }),

  getPipelineResult: (documentId: string): Promise<UploadResponse> =>
    request<UploadResponse>(`/api/v1/documents/${documentId}/pipeline`),

  getExtraction: (documentId: string): Promise<ExtractionResult> =>
    request<ExtractionResult>(`/api/v1/documents/${documentId}/extraction`),

  getValidation: (documentId: string): Promise<ValidationResult> =>
    request<ValidationResult>(`/api/v1/documents/${documentId}/validation`),

  getTampering: (documentId: string): Promise<TamperingResult> =>
    request<TamperingResult>(`/api/v1/documents/${documentId}/tampering`),

  getFaceVerification: (documentId: string): Promise<FaceVerificationResult> =>
    request<FaceVerificationResult>(
      `/api/v1/documents/${documentId}/face-verification`
    ),

  getRiskScore: (documentId: string): Promise<RiskScoreResponse> =>
    request<RiskScoreResponse>(`/api/v1/documents/${documentId}/risk-score`),

  recordDecision: (
    documentId: string,
    payload: DecisionRequest
  ): Promise<DecisionResponse> =>
    request<DecisionResponse>(`/api/v1/documents/${documentId}/decision`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Audit Ledger
  getAuditTrail: (documentId: string): Promise<AuditTrailResponse> =>
    request<AuditTrailResponse>(`/api/v1/audit/${documentId}`),

  verifyAuditChain: (): Promise<ChainVerificationResponse> =>
    request<ChainVerificationResponse>("/api/v1/audit/events/verify"),

  // Command & Analytics
  getSummaryStats: (): Promise<SummaryStats> =>
    request<SummaryStats>("/api/v1/analytics/summary"),

  getRecentScans: (limit = 20): Promise<RecentScan[]> =>
    request<RecentScan[]>(`/api/v1/analytics/scans/recent?limit=${limit}`),

  getHighRiskScans: (limit = 20): Promise<RecentScan[]> =>
    request<RecentScan[]>(`/api/v1/analytics/scans/high-risk?limit=${limit}`),

  getBlacklist: (limit = 100): Promise<BlacklistEntryOut[]> =>
    request<BlacklistEntryOut[]>(`/api/v1/analytics/blacklist?limit=${limit}`),

  addBlacklistEntry: (entry: BlacklistEntryIn): Promise<BlacklistEntryOut> =>
    request<BlacklistEntryOut>("/api/v1/analytics/blacklist", {
      method: "POST",
      body: JSON.stringify(entry),
    }),

  deleteBlacklistEntry: (entryId: string): Promise<void> =>
    request<void>(`/api/v1/analytics/blacklist/${entryId}`, {
      method: "DELETE",
    }),

  // Cross-checkpoint cluster history dossier
  getClusterHistory: (clusterId: string): Promise<ClusterHistoryResponse> =>
    request<ClusterHistoryResponse>(`/api/v1/clusters/${clusterId}`),

  getSecondaryQueue: (): Promise<unknown[]> =>
    request<unknown[]>("/api/v1/documents/secondary-queue"),
};
