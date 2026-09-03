import { NextResponse } from "next/server";

import {
  isSameOriginRequest,
  questionnaireProjection,
  respondBoundDemoQuestionnaire,
} from "../../../../../lib/demo-bridge/server";

export const dynamic = "force-dynamic";

const statusFor = {
  DENIED: 403,
  NOT_FOUND: 404,
  CONFLICT: 409,
  UNSUPPORTED: 501,
  INVALID_RECALL_AT: 422,
  STALE_RESPONSE: 409,
  UNAVAILABLE: 503,
} as const;
const choices = new Set(["LEFT", "RIGHT", "INDISTINGUISHABLE", "SKIP"]);

function noStoreJson(body: object, status: number) {
  return NextResponse.json(body, {
    status,
    headers: { "Cache-Control": "no-store", Vary: "Cookie" },
  });
}

function handleFromRequest(request: Request): string | undefined {
  return request.headers
    .get("cookie")
    ?.match(/(?:^|;\s*)mirror_demo_session=([^;]+)/)?.[1];
}

async function bodyFrom(request: Request) {
  if (
    new URL(request.url).search !== "" ||
    request.headers.get("content-type")?.split(";", 1)[0] !== "application/json"
  )
    return null;
  const body: unknown = await request.json().catch(() => null);
  if (!body || typeof body !== "object" || Array.isArray(body)) return null;
  const value = body as Record<string, unknown>;
  if (
    Object.keys(value).length !== 3 ||
    !Object.hasOwn(value, "presentation_token") ||
    !Object.hasOwn(value, "choice") ||
    !Object.hasOwn(value, "response_latency_ms")
  )
    return null;
  if (
    typeof value.presentation_token !== "string" ||
    !/^[a-f0-9]{64}$/.test(value.presentation_token) ||
    typeof value.choice !== "string" ||
    !choices.has(value.choice) ||
    typeof value.response_latency_ms !== "number" ||
    !Number.isSafeInteger(value.response_latency_ms) ||
    value.response_latency_ms < 0 ||
    value.response_latency_ms > 3_600_000
  )
    return null;
  return {
    presentationToken: value.presentation_token,
    choice: value.choice as "LEFT" | "RIGHT" | "INDISTINGUISHABLE" | "SKIP",
    responseLatencyMs: value.response_latency_ms,
  };
}

export async function POST(request: Request) {
  if (!isSameOriginRequest(request) || request.headers.has("authorization"))
    return noStoreJson({ code: "DENIED" }, 403);
  const body = await bodyFrom(request);
  if (!body) return noStoreJson({ code: "DENIED" }, 403);
  const result = await respondBoundDemoQuestionnaire(
    handleFromRequest(request),
    body,
  );
  const projection = questionnaireProjection(result);
  if (
    result.kind === "QUESTION" ||
    result.kind === "COMPLETED" ||
    result.kind === "CANCELLED" ||
    result.kind === "REJECTED" ||
    result.kind === "FAILED"
  )
    return noStoreJson(projection, 200);
  if (result.kind === "PENDING") return noStoreJson(projection, 503);
  return noStoreJson(projection, statusFor[result.kind]);
}
