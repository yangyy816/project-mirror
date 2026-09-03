import { NextResponse } from "next/server";

import {
  isSameOriginRequest,
  readBoundDemoRecall,
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

export async function GET(request: Request) {
  if (!isSameOriginRequest(request) || request.headers.has("authorization")) {
    return noStoreJson({ code: "DENIED" }, 403);
  }
  const url = new URL(request.url);
  const recallValues = url.searchParams.getAll("recall_at");
  if (url.searchParams.size !== 1 || recallValues.length !== 1) {
    return noStoreJson({ code: "INVALID_RECALL_AT" }, 422);
  }
  const handle = request.headers
    .get("cookie")
    ?.match(/(?:^|;\s*)mirror_demo_session=([^;]+)/)?.[1];
  const result = await readBoundDemoRecall(handle, recallValues[0] ?? null);
  if (result.kind !== "READY") {
    return noStoreJson({ code: result.kind }, statusFor[result.kind]);
  }
  return noStoreJson(
    {
      status: "READY",
      recall_at: result.recallAt,
      context: result.context,
      trace: result.trace,
    },
    200,
  );
}
