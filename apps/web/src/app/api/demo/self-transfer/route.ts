import { NextResponse } from "next/server";

import {
  createBoundDemoSelfTransfer,
  demoSessionCookieName,
  isSameOriginRequest,
  readBoundDemoSelfTransfer,
  selfTransferProjection,
} from "../../../../lib/demo-bridge/server";

export const dynamic = "force-dynamic";
const handle = (request: Request) =>
  request.headers
    .get("cookie")
    ?.match(new RegExp(`(?:^|;\\s*)${demoSessionCookieName}=([^;]+)`))?.[1];
const json = (body: object, status: number) =>
  NextResponse.json(body, {
    status,
    headers: { "Cache-Control": "no-store", Vary: "Cookie" },
  });
const status = (kind: string) =>
  (
    ({
      DENIED: 403,
      NOT_FOUND: 404,
      CONFLICT: 409,
      UNAVAILABLE: 503,
      STALE_RESPONSE: 409,
    }) as Record<string, number>
  )[kind] ?? 503;
const denied = (request: Request) =>
  !isSameOriginRequest(request) || request.headers.has("authorization");
async function exactStart(request: Request) {
  if (
    new URL(request.url).search ||
    request.headers.get("content-type")?.split(";", 1)[0] !== "application/json"
  )
    return false;
  const body = await request.json().catch(() => null);
  return (
    !!body &&
    typeof body === "object" &&
    !Array.isArray(body) &&
    Object.keys(body as object).length === 1 &&
    (body as { action?: unknown }).action === "PROFILE_GUIDED_GEOMETRY_PREVIEW"
  );
}
export async function POST(request: Request) {
  if (denied(request) || !(await exactStart(request)))
    return json({ code: "DENIED" }, 403);
  const result = await createBoundDemoSelfTransfer(handle(request));
  return json(
    selfTransferProjection(result),
    result.kind === "PENDING"
      ? 202
      : result.kind === "PREVIEW_READY" ||
          result.kind === "NO_COMPATIBLE_CASE" ||
          result.kind === "FAILED"
        ? 200
        : status(result.kind),
  );
}
export async function GET(request: Request) {
  if (denied(request) || new URL(request.url).search || request.body !== null)
    return json({ code: "DENIED" }, 403);
  const result = await readBoundDemoSelfTransfer(handle(request));
  return json(
    selfTransferProjection(result),
    result.kind === "PENDING"
      ? 200
      : result.kind === "PREVIEW_READY" ||
          result.kind === "REFERENCE_PROFILE_PENDING" ||
          result.kind === "REFERENCE_PROFILE_READY" ||
          result.kind === "NO_COMPATIBLE_CASE" ||
          result.kind === "FAILED"
        ? 200
        : status(result.kind),
  );
}
