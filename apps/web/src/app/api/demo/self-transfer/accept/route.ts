import { NextResponse } from "next/server";
import {
  acceptBoundDemoSelfTransfer,
  demoSessionCookieName,
  isSameOriginRequest,
  selfTransferProjection,
} from "../../../../../lib/demo-bridge/server";
export const dynamic = "force-dynamic";
const json = (body: object, status: number) =>
  NextResponse.json(body, {
    status,
    headers: { "Cache-Control": "no-store", Vary: "Cookie" },
  });
export async function POST(request: Request) {
  const invalid =
    !isSameOriginRequest(request) ||
    request.headers.has("authorization") ||
    new URL(request.url).search ||
    request.headers.get("content-type")?.split(";", 1)[0] !==
      "application/json";
  const body = invalid ? null : await request.json().catch(() => null);
  if (
    !body ||
    typeof body !== "object" ||
    Array.isArray(body) ||
    Object.keys(body).length !== 1 ||
    (body as { outcome?: unknown }).outcome !==
      "FINAL_SAVE_AND_USE_AS_REFERENCE"
  )
    return json({ code: "DENIED" }, 403);
  const handle = request.headers
    .get("cookie")
    ?.match(new RegExp(`(?:^|;\\s*)${demoSessionCookieName}=([^;]+)`))?.[1];
  const result = await acceptBoundDemoSelfTransfer(handle);
  const code =
    result.kind === "REFERENCE_PROFILE_PENDING" ||
    result.kind === "REFERENCE_PROFILE_READY"
      ? 202
      : result.kind === "CONFLICT"
        ? 409
        : result.kind === "DENIED"
          ? 403
          : result.kind === "UNAVAILABLE"
            ? 503
            : 409;
  return json(selfTransferProjection(result), code);
}
