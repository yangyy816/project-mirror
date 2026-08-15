export type AuthErrorCode =
  | "authentication_failed"
  | "authentication_throttled"
  | "idempotency_conflict"
  | "network_error"
  | "csrf_unavailable"
  | "crypto_unavailable";

const publicCodes = new Set<AuthErrorCode>([
  "authentication_failed",
  "authentication_throttled",
  "idempotency_conflict",
]);

export class BrowserAuthError extends Error {
  readonly code: AuthErrorCode;
  readonly status: number | null;

  constructor(code: AuthErrorCode, status: number | null = null) {
    super("认证请求未完成，请稍后重试。");
    this.name = "BrowserAuthError";
    this.code = code;
    this.status = status;
  }
}

export function sanitizeAuthFailure(
  status: number,
  candidate: unknown,
): BrowserAuthError {
  const code =
    typeof candidate === "object" &&
    candidate !== null &&
    "code" in candidate &&
    typeof candidate.code === "string" &&
    publicCodes.has(candidate.code as AuthErrorCode)
      ? (candidate.code as AuthErrorCode)
      : "authentication_failed";
  return new BrowserAuthError(code, status);
}
