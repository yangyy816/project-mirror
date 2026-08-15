import { createServer } from "node:http";

const host = "127.0.0.1";
const port = 4400;
const appOrigin = "http://127.0.0.1:4300";
const challengeId = "c".repeat(32);
const userId = "d".repeat(32);
const recordId = "e".repeat(32);
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
        "Authorization, Content-Type, Idempotency-Key, X-CSRF-Token",
      "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    });
    response.end();
    return;
  }

  if (request.method === "GET" && url.pathname === "/health") {
    send(response, 200, { status: "live" });
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
    });
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
