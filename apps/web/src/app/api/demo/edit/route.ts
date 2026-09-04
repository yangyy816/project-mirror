import { NextResponse } from "next/server";

import {
  createBoundDemoEdit,
  editProjection,
  isSameOriginRequest,
  readBoundDemoEdit,
  validDemoEditRequest,
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

function denied(request: Request): boolean {
  return !isSameOriginRequest(request) || request.headers.has("authorization");
}

async function editRequest(request: Request) {
  if (
    new URL(request.url).search !== "" ||
    request.headers.get("content-type")?.split(";", 1)[0] !== "application/json"
  )
    return null;
  const body: unknown = await request.json().catch(() => null);
  if (!body || typeof body !== "object" || Array.isArray(body)) return null;
  const value = body as Record<string, unknown>;
  if (
    Object.keys(value).length !== 2 ||
    !Object.hasOwn(value, "operation") ||
    !Object.hasOwn(value, "value_ppm")
  )
    return null;
  const parsed = { operation: value.operation, valuePpm: value.value_ppm };
  return validDemoEditRequest(parsed) ? parsed : null;
}

async function bodyless(request: Request) {
  if (new URL(request.url).search !== "") return false;
  if (request.body === null) return true;
  return (
    request.headers.get("content-length") === "0" &&
    request.headers.get("transfer-encoding") === null
  );
}

function responseFor(
  result: Awaited<ReturnType<typeof readBoundDemoEdit>>,
  pendingStatus: number,
) {
  const body = editProjection(result);
  if (result.kind === "PENDING") return noStoreJson(body, pendingStatus);
  if (
    result.kind === "IMAGE_VERSION_READY" ||
    result.kind === "REJECTED" ||
    result.kind === "FAILED" ||
    result.kind === "CANCELLED"
  )
    return noStoreJson(body, 200);
  return noStoreJson(body, statusFor[result.kind]);
}

export async function POST(request: Request) {
  if (denied(request)) return noStoreJson({ code: "DENIED" }, 403);
  const body = await editRequest(request);
  if (!body) return noStoreJson({ code: "DENIED" }, 403);
  return responseFor(
    await createBoundDemoEdit(handleFromRequest(request), body),
    202,
  );
}

export async function GET(request: Request) {
  if (denied(request) || !(await bodyless(request)))
    return noStoreJson({ code: "DENIED" }, 403);
  return responseFor(await readBoundDemoEdit(handleFromRequest(request)), 200);
}
