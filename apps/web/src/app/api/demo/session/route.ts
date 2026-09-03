import { NextResponse } from "next/server";

import {
  createBoundDemoSession,
  demoSessionCookieName,
  demoSessionPath,
  isSameOriginRequest,
  removeBoundDemoSession,
  sessionCookieOptions,
} from "../../../../lib/demo-bridge/server";

export const dynamic = "force-dynamic";

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

async function isValidSessionRequest(request: Request): Promise<boolean> {
  const url = new URL(request.url);
  if (url.search !== "") return false;
  if (request.headers.get("transfer-encoding") !== null) return false;
  const contentLength = request.headers.get("content-length");
  if (contentLength !== null && contentLength !== "0") return false;
  if (request.body === null) return true;
  const reader = request.body.getReader();
  const first = await reader.read();
  if (!first.done) {
    await reader.cancel().catch(() => undefined);
    return false;
  }
  return true;
}

export async function POST(request: Request) {
  if (
    !isSameOriginRequest(request) ||
    request.headers.has("authorization") ||
    !(await isValidSessionRequest(request))
  ) {
    return noStoreJson({ code: "DENIED" }, 403);
  }
  const session = await createBoundDemoSession(handleFromRequest(request));
  if (!session) return noStoreJson({ code: "UNAVAILABLE" }, 503);

  const response = noStoreJson({ status: "SESSION_READY" }, 201);
  response.cookies.set(
    demoSessionCookieName,
    session.handle,
    sessionCookieOptions(session.maxAge),
  );
  return response;
}

export async function DELETE(request: Request) {
  if (
    !isSameOriginRequest(request) ||
    request.headers.has("authorization") ||
    !(await isValidSessionRequest(request))
  ) {
    return noStoreJson({ code: "DENIED" }, 403);
  }
  removeBoundDemoSession(handleFromRequest(request));
  const response = noStoreJson({ status: "LOGGED_OUT" }, 200);
  response.cookies.set(demoSessionCookieName, "", {
    httpOnly: true,
    sameSite: "strict",
    path: demoSessionPath,
    maxAge: 0,
    secure: process.env.NODE_ENV === "production",
  });
  return response;
}
