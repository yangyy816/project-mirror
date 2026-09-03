import { NextResponse } from "next/server";

import {
  createBoundDemoAnalysis,
  isSameOriginRequest,
  readBoundDemoAnalysis,
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

async function isValidBodylessRequest(request: Request): Promise<boolean> {
  const url = new URL(request.url);
  if (url.search !== "") return false;
  if (request.body === null) return true;
  return (
    request.headers.get("content-length") === "0" &&
    request.headers.get("transfer-encoding") === null
  );
}

function deniedRequest(request: Request): boolean {
  return !isSameOriginRequest(request) || request.headers.has("authorization");
}

export async function POST(request: Request) {
  if (deniedRequest(request) || !(await isValidBodylessRequest(request))) {
    return noStoreJson({ code: "DENIED" }, 403);
  }
  const result = await createBoundDemoAnalysis(handleFromRequest(request));
  if (result.kind === "PENDING") return noStoreJson({ status: "PENDING" }, 202);
  return noStoreJson(
    { code: result.kind },
    statusFor[result.kind as keyof typeof statusFor],
  );
}

export async function GET(request: Request) {
  if (deniedRequest(request) || !(await isValidBodylessRequest(request))) {
    return noStoreJson({ code: "DENIED" }, 403);
  }
  const result = await readBoundDemoAnalysis(handleFromRequest(request));
  if (result.kind === "PENDING") return noStoreJson({ status: "PENDING" }, 200);
  if (result.kind === "COMPLETED") {
    return noStoreJson(
      {
        status: "COMPLETED",
        analysis_state: result.analysisState,
        self_state: result.selfState,
      },
      200,
    );
  }
  if (
    result.kind === "CANCELLED" ||
    result.kind === "REJECTED" ||
    result.kind === "FAILED"
  ) {
    return noStoreJson({ status: result.kind }, 200);
  }
  return noStoreJson({ code: result.kind }, statusFor[result.kind]);
}
