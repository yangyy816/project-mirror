import { NextResponse } from "next/server";

import {
  demoSessionCookieName,
  fetchBoundDemoSelfTransferMedia,
  isSameOriginRequest,
} from "../../../../../../../lib/demo-bridge/server";

export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  context: { params: Promise<{ media_token: string; side: string }> },
) {
  const { media_token: token, side } = await context.params;
  if (
    !isSameOriginRequest(request) ||
    request.headers.has("authorization") ||
    new URL(request.url).search ||
    request.body !== null ||
    (side !== "INPUT" && side !== "RESULT")
  )
    return NextResponse.json({ code: "DENIED" }, { status: 403 });
  const handle = request.headers
    .get("cookie")
    ?.match(new RegExp(`(?:^|;\\s*)${demoSessionCookieName}=([^;]+)`))?.[1];
  const response = await fetchBoundDemoSelfTransferMedia(handle, token, side);
  if (!response)
    return NextResponse.json({ code: "NOT_FOUND" }, { status: 404 });
  const headers = new Headers(response.headers);
  headers.set("Vary", "Cookie");
  return new NextResponse(response.body, { status: response.status, headers });
}
