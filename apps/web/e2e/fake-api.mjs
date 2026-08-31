import { createServer } from "node:http";

const host = "localhost";
const port = 4400;
const appOrigin = "http://localhost:4300";
const challengeId = "c".repeat(32);
const userId = "d".repeat(32);
const recordId = "e".repeat(32);
const assetId = "a".repeat(32);
const exportId = "b".repeat(32);
const deletionRequestId = "f".repeat(32);
const jobId = "9".repeat(32);
const demoSessionId = "1".repeat(32);
const demoDigest = "f".repeat(64);
const demoBearer = "x".repeat(32);
const refreshCookie =
  "mirror_refresh=synthetic-refresh; HttpOnly; SameSite=Lax; Path=/";
const csrfCookie = "mirror_csrf=synthetic-csrf; SameSite=Lax; Path=/";

let state;

function reset() {
  state = {
    session: false,
    adult: false,
    policy: false,
    lastInvitePresent: false,
    challengeCount: 0,
    assetPresent: true,
    exportStatus: null,
    exportPolls: 0,
    accountDeletionStatus: null,
    accountDeletionPolls: 0,
    failNextAssetList: false,
    demoRecallAts: [],
    demoRequestCount: 0,
    demoDigestMismatch: false,
  };
}

reset();

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": appOrigin,
    "Access-Control-Allow-Credentials": "true",
    Vary: "Origin",
  };
}

function send(response, status, body, headers = {}) {
  const payload = body === null ? null : JSON.stringify(body);
  response.writeHead(status, {
    ...corsHeaders(),
    ...(payload === null ? {} : { "Content-Type": "application/json" }),
    ...headers,
  });
  response.end(payload);
}

function error(response, status, code = "authentication_failed") {
  send(response, status, {
    code,
    message: "请求未完成。",
    request_id: "e2e-request",
    details: null,
  });
}

async function jsonBody(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
}

function isAuthorized(request) {
  return state.session && request.headers.authorization?.startsWith("Bearer ");
}

function hasCsrf(request) {
  return (
    request.headers["x-csrf-token"] === "synthetic-csrf" &&
    request.headers.cookie?.includes("mirror_csrf=synthetic-csrf")
  );
}

function currentUser() {
  const requirements = [];
  if (!state.adult) requirements.push("age_assurance");
  if (!state.policy) requirements.push("policy_acceptance");
  const active = requirements.length === 0;
  return {
    user_id: userId,
    status: active ? "active" : "pending",
    scope: active ? "active" : "pending",
    onboarding_requirements: requirements,
  };
}

const server = createServer(async (request, response) => {
  const url = new URL(request.url ?? "/", `http://${host}:${port}`);

  if (request.method === "OPTIONS") {
    response.writeHead(204, {
      ...corsHeaders(),
      "Access-Control-Allow-Headers":
        "Authorization, Content-Type, Idempotency-Key, X-CSRF-Token, X-Mirror-Grant",
      "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    });
    response.end();
    return;
  }

  if (request.method === "GET" && url.pathname === "/health") {
    send(response, 200, { status: "live" });
    return;
  }

  if (request.method === "GET" && url.pathname === "/health/live") {
    send(response, 200, { status: "live", version: "e2e" });
    return;
  }

  if (request.method === "GET" && url.pathname === "/health/ready") {
    send(response, 200, {
      status: "ready",
      version: "e2e",
      dependencies: { database: "ready", redis: "ready" },
    });
    return;
  }

  if (
    request.method === "GET" &&
    url.pathname === `/api/v1/demo/sessions/${demoSessionId}/context`
  ) {
    if (request.headers.authorization !== `Bearer ${demoBearer}`) {
      error(response, 401);
      return;
    }
    state.demoRecallAts.push(url.searchParams.get("recall_at"));
    state.demoRequestCount += 1;
    send(response, 200, {
      session_id: demoSessionId,
      profile_id: "2".repeat(32),
      compilation_digest: demoDigest,
      expires_at: "2099-01-01T00:15:00Z",
    });
    return;
  }

  if (
    request.method === "GET" &&
    url.pathname === `/api/v1/demo/traces/${demoSessionId}`
  ) {
    if (request.headers.authorization !== `Bearer ${demoBearer}`) {
      error(response, 401);
      return;
    }
    state.demoRecallAts.push(url.searchParams.get("recall_at"));
    state.demoRequestCount += 1;
    send(response, 200, {
      session_id: demoSessionId,
      context_compilation_id: "3".repeat(32),
      evidence_digest: state.demoDigestMismatch ? "e".repeat(64) : demoDigest,
    });
    return;
  }

  if (request.method === "POST" && url.pathname === "/__test/reset") {
    reset();
    send(response, 204, null, {
      "Set-Cookie": [
        "mirror_refresh=; HttpOnly; Max-Age=0; SameSite=Lax; Path=/",
        "mirror_csrf=; Max-Age=0; SameSite=Lax; Path=/",
      ],
    });
    return;
  }

  if (request.method === "GET" && url.pathname === "/__test/state") {
    send(response, 200, {
      session: state.session,
      active: state.adult && state.policy,
      last_invite_present: state.lastInvitePresent,
      challenge_count: state.challengeCount,
      asset_present: state.assetPresent,
      export_status: state.exportStatus,
      account_deletion_status: state.accountDeletionStatus,
      demo_recall_ats: state.demoRecallAts,
      demo_request_count: state.demoRequestCount,
    });
    return;
  }

  if (request.method === "POST" && url.pathname === "/__test/fail-next") {
    const body = await jsonBody(request);
    if (body.target === "assets") state.failNextAssetList = true;
    if (body.target === "demo-digest-mismatch") state.demoDigestMismatch = true;
    send(response, 204, null);
    return;
  }

  if (request.method === "GET" && url.pathname === "/policies/privacy") {
    response.writeHead(200, {
      ...corsHeaders(),
      "Content-Type": "text/html; charset=utf-8",
    });
    response.end(
      "<!doctype html><title>隐私政策测试文档</title><h1>隐私政策测试文档</h1>",
    );
    return;
  }

  if (request.method === "GET" && url.pathname === "/age/verify") {
    const nonce = JSON.stringify(url.searchParams.get("state") ?? "");
    const target = JSON.stringify(appOrigin);
    response.writeHead(200, {
      ...corsHeaders(),
      "Content-Type": "text/html; charset=utf-8",
    });
    response.end(`<!doctype html><title>年龄核验测试</title><script>
      window.opener.postMessage({
        type: "mirror.age-assurance.result.v1",
        state: ${nonce},
        credential: "synthetic-age-credential"
      }, ${target});
      window.close();
    </script>`);
    return;
  }

  if (
    request.method === "POST" &&
    url.pathname === "/api/v1/auth/sms-challenges"
  ) {
    const body = await jsonBody(request);
    state.lastInvitePresent = typeof body.invite_code === "string";
    state.challengeCount += 1;
    send(
      response,
      202,
      { challenge_id: challengeId, expires_at: "2099-01-01T00:00:00Z" },
      { "Set-Cookie": csrfCookie },
    );
    return;
  }

  if (request.method === "GET" && url.pathname === "/api/v1/assets") {
    if (!isAuthorized(request)) {
      error(response, 401);
      return;
    }
    if (state.failNextAssetList) {
      state.failNextAssetList = false;
      error(response, 503, "temporarily_unavailable");
      return;
    }
    send(response, 200, {
      assets: state.assetPresent
        ? [
            {
              asset_id: assetId,
              asset_role: "synthetic",
              mime_type: "image/jpeg",
              byte_size: 128,
              width: 32,
              height: 24,
              created_at: "2099-01-01T00:00:00Z",
            },
          ]
        : [],
    });
    return;
  }

  if (
    request.method === "GET" &&
    url.pathname === `/api/v1/assets/${assetId}`
  ) {
    if (!isAuthorized(request) || !state.assetPresent) {
      error(response, state.assetPresent ? 401 : 404, "not_found");
      return;
    }
    send(response, 200, {
      asset_id: assetId,
      asset_role: "synthetic",
      mime_type: "image/jpeg",
      byte_size: 128,
      width: 32,
      height: 24,
      created_at: "2099-01-01T00:00:00Z",
    });
    return;
  }

  if (
    request.method === "POST" &&
    url.pathname === `/api/v1/assets/${assetId}/download-grants`
  ) {
    if (!isAuthorized(request) || !state.assetPresent) {
      error(response, state.assetPresent ? 401 : 404, "not_found");
      return;
    }
    send(response, 201, {
      method: "GET",
      url: `http://${host}:${port}/__download/asset`,
      required_headers: { "X-Mirror-Grant": "synthetic-asset-grant" },
      expires_at: "2099-01-01T00:00:00Z",
    });
    return;
  }

  if (
    request.method === "GET" &&
    url.pathname === "/__download/asset" &&
    request.headers["x-mirror-grant"] === "synthetic-asset-grant" &&
    state.assetPresent
  ) {
    response.writeHead(200, {
      ...corsHeaders(),
      "Content-Type": "image/jpeg",
      "Content-Length": "4",
    });
    response.end(Buffer.from([0xff, 0xd8, 0xff, 0xd9]));
    return;
  }

  if (
    request.method === "DELETE" &&
    url.pathname === `/api/v1/assets/${assetId}`
  ) {
    if (!isAuthorized(request) || !state.assetPresent) {
      error(response, state.assetPresent ? 401 : 404, "not_found");
      return;
    }
    state.assetPresent = false;
    send(response, 202, {
      deletion_request_id: deletionRequestId,
      job_id: jobId,
      status: "requested",
    });
    return;
  }

  if (
    request.method === "POST" &&
    url.pathname === "/api/v1/users/me/data-exports"
  ) {
    if (!isAuthorized(request)) {
      error(response, 401);
      return;
    }
    state.exportStatus = "requested";
    state.exportPolls = 0;
    send(response, 202, {
      export_id: exportId,
      job_id: jobId,
      status: state.exportStatus,
      schema_version: "mirror-data-export-v1",
      requested_at: "2099-01-01T00:00:00Z",
      ready_at: null,
      expires_at: null,
    });
    return;
  }

  if (
    request.method === "GET" &&
    url.pathname === `/api/v1/users/me/data-exports/${exportId}`
  ) {
    if (!isAuthorized(request) || state.exportStatus === null) {
      error(response, state.exportStatus === null ? 404 : 401, "not_found");
      return;
    }
    state.exportPolls += 1;
    state.exportStatus = state.exportPolls >= 2 ? "ready" : "processing";
    send(response, 200, {
      export_id: exportId,
      job_id: jobId,
      status: state.exportStatus,
      schema_version: "mirror-data-export-v1",
      requested_at: "2099-01-01T00:00:00Z",
      ready_at: state.exportStatus === "ready" ? "2099-01-01T00:00:01Z" : null,
      expires_at:
        state.exportStatus === "ready" ? "2099-01-02T00:00:01Z" : null,
    });
    return;
  }

  if (
    request.method === "POST" &&
    url.pathname === `/api/v1/users/me/data-exports/${exportId}/download-grants`
  ) {
    if (!isAuthorized(request) || state.exportStatus !== "ready") {
      error(response, 404, "not_found");
      return;
    }
    send(response, 201, {
      method: "GET",
      url: `http://${host}:${port}/__download/export`,
      required_headers: { "X-Mirror-Grant": "synthetic-export-grant" },
      expires_at: "2099-01-01T00:00:00Z",
    });
    return;
  }

  if (
    request.method === "GET" &&
    url.pathname === "/__download/export" &&
    request.headers["x-mirror-grant"] === "synthetic-export-grant"
  ) {
    response.writeHead(200, {
      ...corsHeaders(),
      "Content-Type": "application/zip",
      "Content-Length": "4",
    });
    response.end(Buffer.from("PK\u0005\u0006"));
    return;
  }

  if (
    request.method === "POST" &&
    url.pathname === "/api/v1/users/me/deletion-requests"
  ) {
    if (!isAuthorized(request)) {
      error(response, 401);
      return;
    }
    state.accountDeletionStatus = "requested";
    state.accountDeletionPolls = 0;
    state.session = false;
    send(response, 202, {
      deletion_request_id: deletionRequestId,
      job_id: jobId,
      status: state.accountDeletionStatus,
      requested_at: "2099-01-01T00:00:00Z",
      completed_at: null,
    });
    return;
  }

  if (
    request.method === "GET" &&
    url.pathname === "/api/v1/users/me/deletion-requests/current"
  ) {
    if (
      !request.headers.authorization?.startsWith("Bearer ") ||
      state.accountDeletionStatus === null
    ) {
      error(response, 401);
      return;
    }
    state.accountDeletionPolls += 1;
    state.accountDeletionStatus =
      state.accountDeletionPolls >= 2 ? "completed" : "processing";
    send(response, 200, {
      deletion_request_id: deletionRequestId,
      job_id: jobId,
      status: state.accountDeletionStatus,
      requested_at: "2099-01-01T00:00:00Z",
      completed_at:
        state.accountDeletionStatus === "completed"
          ? "2099-01-01T00:00:01Z"
          : null,
    });
    return;
  }

  if (request.method === "POST" && url.pathname === "/api/v1/auth/sessions") {
    const body = await jsonBody(request);
    if (body.challenge_id !== challengeId || body.otp !== "123456") {
      error(response, 401);
      return;
    }
    state.session = true;
    send(
      response,
      201,
      {
        access_token: "synthetic-access",
        token_type: "Bearer",
        scope: "pending",
      },
      { "Set-Cookie": [refreshCookie, csrfCookie] },
    );
    return;
  }

  if (
    request.method === "POST" &&
    url.pathname === "/api/v1/auth/token/refresh"
  ) {
    if (
      !state.session ||
      !request.headers.cookie?.includes("mirror_refresh=synthetic-refresh") ||
      !hasCsrf(request)
    ) {
      error(response, 401);
      return;
    }
    const scope = state.adult && state.policy ? "active" : "pending";
    send(
      response,
      200,
      {
        access_token: "synthetic-refreshed-access",
        token_type: "Bearer",
        scope,
      },
      { "Set-Cookie": [refreshCookie, csrfCookie] },
    );
    return;
  }

  if (request.method === "GET" && url.pathname === "/api/v1/users/me") {
    if (!isAuthorized(request)) {
      error(response, 401);
      return;
    }
    send(response, 200, currentUser());
    return;
  }

  if (
    request.method === "POST" &&
    url.pathname === "/api/v1/users/me/age-assurances"
  ) {
    const body = await jsonBody(request);
    if (
      !isAuthorized(request) ||
      body.credential !== "synthetic-age-credential"
    ) {
      error(response, 401);
      return;
    }
    state.adult = true;
    send(response, 201, {
      record_id: recordId,
      result: "verified",
      activated: state.policy,
    });
    return;
  }

  if (
    request.method === "POST" &&
    url.pathname === "/api/v1/users/me/policy-acceptances"
  ) {
    const body = await jsonBody(request);
    if (
      !isAuthorized(request) ||
      body.document_code !== "privacy" ||
      body.document_version !== "e2e-v1" ||
      body.document_digest !== "a".repeat(64)
    ) {
      error(response, 401);
      return;
    }
    state.policy = true;
    send(response, 201, { activated: state.adult });
    return;
  }

  if (
    request.method === "DELETE" &&
    url.pathname === "/api/v1/auth/sessions/current"
  ) {
    if (!isAuthorized(request) || !hasCsrf(request)) {
      error(response, 401);
      return;
    }
    state.session = false;
    send(response, 204, null, {
      "Set-Cookie": [
        "mirror_refresh=; HttpOnly; Max-Age=0; SameSite=Lax; Path=/",
        "mirror_csrf=; Max-Age=0; SameSite=Lax; Path=/",
      ],
    });
    return;
  }

  error(response, 404, "not_found");
});

server.listen(port, host, () => {
  process.stdout.write(
    `Project Mirror E2E Fake API listening on http://${host}:${port}\n`,
  );
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => server.close(() => process.exit(0)));
}
