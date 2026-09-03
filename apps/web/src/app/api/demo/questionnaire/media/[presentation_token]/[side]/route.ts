import { NextResponse } from "next/server";

import { fetchBoundQuestionnaireMedia } from "../../../../../../../lib/demo-bridge/server";

export const dynamic = "force-dynamic";

function handleFromRequest(request: Request): string | undefined {
  return request.headers
    .get("cookie")
    ?.match(/(?:^|;\s*)mirror_demo_session=([^;]+)/)?.[1];
}

export async function GET(
  request: Request,
  context: { params: Promise<{ presentation_token: string; side: string }> },
) {
  const { presentation_token: token, side } = await context.params;
  if (
    new URL(request.url).search !== "" ||
    request.headers.has("authorization") ||
    !/^[a-f0-9]{64}$/.test(token) ||
    (side !== "LEFT" && side !== "RIGHT")
  )
    return new NextResponse(null, {
      status: 403,
      headers: { "Cache-Control": "no-store", Vary: "Cookie" },
    });
  const media = await fetchBoundQuestionnaireMedia(
    handleFromRequest(request),
    token,
    side,
  );
  if (!media || !media.body)
    return new NextResponse(null, {
      status: 404,
      headers: { "Cache-Control": "no-store", Vary: "Cookie" },
    });
  return new NextResponse(media.body, {
    status: 200,
    headers: {
      "Content-Type": "image/jpeg",
      "Content-Length": media.headers.get("content-length")!,
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
      Vary: "Cookie",
    },
  });
}
