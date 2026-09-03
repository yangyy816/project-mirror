import { NextResponse } from "next/server";

import {
  createBoundDemoQuestionnaire,
  isSameOriginRequest,
  questionnaireProjection,
  readBoundDemoQuestionnaire,
} from "../../../../lib/demo-bridge/server";

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

async function isBodyless(request: Request): Promise<boolean> {
  const url = new URL(request.url);
  if (url.search !== "") return false;
  if (request.body === null) return true;
  return (
    request.headers.get("content-length") === "0" &&
    request.headers.get("transfer-encoding") === null
  );
}

function denied(request: Request): boolean {
  return !isSameOriginRequest(request) || request.headers.has("authorization");
}

function responseFor(
  result: Awaited<ReturnType<typeof readBoundDemoQuestionnaire>>,
  pendingStatus: number,
) {
  const body = questionnaireProjection(result);
  if (result.kind === "PENDING") return noStoreJson(body, pendingStatus);
  if (
    result.kind === "QUESTION" ||
    result.kind === "COMPLETED" ||
    result.kind === "CANCELLED" ||
    result.kind === "REJECTED" ||
    result.kind === "FAILED"
  )
    return noStoreJson(body, 200);
  return noStoreJson(body, statusFor[result.kind]);
}

export async function POST(request: Request) {
  if (denied(request) || !(await isBodyless(request)))
    return noStoreJson({ code: "DENIED" }, 403);
  return responseFor(
    await createBoundDemoQuestionnaire(handleFromRequest(request)),
    202,
  );
}

export async function GET(request: Request) {
  if (denied(request) || !(await isBodyless(request)))
    return noStoreJson({ code: "DENIED" }, 403);
  return responseFor(
    await readBoundDemoQuestionnaire(handleFromRequest(request)),
    200,
  );
}
