// Task-scoped stdin operator. Private startup injects the bearer; callers never see it.
import http from "node:http";
import net from "node:net";
import { randomBytes } from "node:crypto";
import { createInterface } from "node:readline";

const origin = new URL(process.env.API_BASE_URL ?? "http://127.0.0.1:48080");
const bearer = process.env.DEMO_BEARER_TOKEN;
if (
  origin.protocol !== "http:" ||
  !["localhost", "127.0.0.1", "[::1]"].includes(origin.hostname) ||
  origin.username ||
  origin.password
)
  throw new Error("LOOPBACK_ORIGIN_REQUIRED");
if (!bearer || bearer.length < 16) throw new Error("PRIVATE_BEARER_REQUIRED");
const keys = new Map();
const commands = new Map();
const allowedFields = new Set([
  "status",
  "code",
  "kind",
  "state",
  "job_id",
  "session_id",
  "analysis_id",
  "profile_id",
  "reference_profile_id",
  "run_id",
  "step_id",
  "question_pair_id",
  "editing_session_id",
  "edit_plan_id",
  "image_version_id",
  "tool_run_id",
  "context_compilation_id",
  "event_id",
  "episode_id",
  "capability",
  "target",
  "target_type",
  "target_id",
  "authority_digest",
  "job_binding_digest",
  "compilation_digest",
  "profile_digest",
  "evidence_digest",
  "observation_digest",
  "self_state_id",
  "request_digest",
  "content_digest",
  "plan_digest",
  "image_version_digest",
  "version_kind",
  "sequence",
  "parent_image_version_id",
  "result_code",
  "finalized_at",
  "expires_at",
  "completed_at",
  "created_at",
  "generation",
  "compilation_watermark",
  "learning_enabled",
  "profiles",
  "identities",
  "identity_id",
  "synthetic_identity_id",
  "admission_status",
  "reference_profile_job_id",
  "queue_state",
  "event_type",
  "event_digest",
  "replayed",
  "reason_codes",
  "step_sequence",
  "run_version",
  "preview",
  "dimension_key",
  "direction",
  "step_ppm",
  "selection_policy_version",
]);
function redact(value) {
  if (Array.isArray(value)) return value.map(redact);
  if (value && typeof value === "object")
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => allowedFields.has(key))
        .map(([key, item]) => [key, redact(item)]),
    );
  if (typeof value === "string" && !/^[A-Za-z0-9_.:+-]{1,128}$/.test(value))
    return "VALUE_WITHHELD";
  return value;
}
function request(input) {
  const url = new URL(input.path, origin);
  if (
    url.origin !== origin.origin ||
    !url.pathname.startsWith("/api/v1/demo/") ||
    !["GET", "POST"].includes(input.method)
  )
    throw new Error("OUTSIDE_DEMO_SCOPE");
  const data = input.body === undefined ? null : JSON.stringify(input.body);
  if (input.method === "GET" && data !== null)
    throw new Error("GET_BODY_FORBIDDEN");
  const headers = { Authorization: `Bearer ${bearer}` };
  if (input.method === "POST") {
    if (
      typeof input.key_ref !== "string" ||
      !/^[a-z0-9-]{1,64}$/.test(input.key_ref)
    )
      throw new Error("KEY_REFERENCE_REQUIRED");
    if (!keys.has(input.key_ref))
      keys.set(input.key_ref, randomBytes(32).toString("hex"));
    headers["Idempotency-Key"] = keys.get(input.key_ref);
  }
  if (data !== null) {
    headers["Content-Type"] = "application/json";
    headers["Content-Length"] = Buffer.byteLength(data);
  }
  return new Promise((resolve, reject) => {
    const req = http.request(url, { method: input.method, headers }, (res) => {
      const chunks = [];
      let size = 0;
      res.on("data", (chunk) => {
        size += chunk.length;
        if (size > 2_000_000) req.destroy(new Error("RESPONSE_LIMIT"));
        else chunks.push(chunk);
      });
      res.on("end", () => {
        try {
          resolve({
            http: res.statusCode,
            body: redact(JSON.parse(Buffer.concat(chunks).toString("utf8"))),
          });
        } catch {
          resolve({
            http: res.statusCode,
            error: "NON_JSON_RESPONSE_WITHHELD",
          });
        }
      });
      res.on("error", reject);
    });
    req.setTimeout(30000, () =>
      req.destroy(new Error("REQUEST_TIMEOUT_OUTCOME_UNKNOWN")),
    );
    req.on("error", reject);
    if (data !== null) req.write(data);
    req.end();
  });
}
const emit = (value) => process.stdout.write(JSON.stringify(value) + "\n");
async function processLine(line, send) {
  let id;
  try {
    const input = JSON.parse(line);
    id = input.id;
    if (typeof id !== "string" || !/^[a-z0-9-]{1,64}$/.test(id))
      throw new Error("COMMAND_ID_REQUIRED");
    const previous = commands.get(id);
    if (previous) {
      if (previous.input !== line) throw new Error("COMMAND_COLLISION");
      send(await previous.result);
      return;
    }
    send({ id, phase: "REQUEST_STARTING" });
    const result = request(input).then((body) => ({ id, result: body }));
    commands.set(id, { input: line, result });
    send(await result);
  } catch (error) {
    const safe = [
      "OUTSIDE_DEMO_SCOPE",
      "GET_BODY_FORBIDDEN",
      "KEY_REFERENCE_REQUIRED",
      "COMMAND_ID_REQUIRED",
      "COMMAND_COLLISION",
      "RESPONSE_LIMIT",
      "REQUEST_TIMEOUT_OUTCOME_UNKNOWN",
    ];
    send({
      id,
      error: safe.includes(error?.message)
        ? error.message
        : "REQUEST_FAILED_DETAILS_WITHHELD",
    });
  }
}

const pipe = process.env.MIRROR_DEMO_CONTROL_PIPE;
if (pipe) {
  if (
    process.platform !== "win32" ||
    !/^mirror-d12-[a-z0-9-]{1,64}$/.test(pipe)
  )
    throw new Error("CONTROL_PIPE_NAME_INVALID");
  const server = net.createServer((socket) => {
    socket.on("error", () => {});
    const lines = createInterface({ input: socket, crlfDelay: Infinity });
    void (async () => {
      for await (const line of lines)
        await processLine(line, (value) => {
          if (!socket.destroyed) socket.write(JSON.stringify(value) + "\n");
        });
    })().catch(() => socket.destroy());
  });
  server.listen(
    { path: "\\\\.\\pipe\\" + pipe, readableAll: false, writableAll: false },
    () =>
      emit({
        status: "PRIVATE_API_OPERATOR_READY",
        credentialPresent: true,
        transport: "OWNER_LOCAL_PIPE",
      }),
  );
  server.on("error", () => {
    emit({ error: "CONTROL_PIPE_BIND_FAILED" });
    process.exitCode = 1;
  });
} else {
  emit({
    status: "PRIVATE_API_OPERATOR_READY",
    credentialPresent: true,
    transport: "STDIN",
  });
  for await (const line of createInterface({
    input: process.stdin,
    crlfDelay: Infinity,
  }))
    await processLine(line, emit);
}
