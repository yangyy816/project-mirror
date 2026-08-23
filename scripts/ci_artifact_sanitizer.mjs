import { readFile, writeFile } from "node:fs/promises";

const LICENSE_TEXT = /^[A-Za-z0-9 .()+-]{1,160}$/;
const PACKAGE_NAME = /^@?[A-Za-z0-9._/-]{1,256}$/;
const VERSION = /^[A-Za-z0-9._+-]{1,128}$/;
const SERVICE = /^[A-Za-z0-9._-]{1,128}$/;
const STATE = /^[A-Za-z0-9._ -]{0,128}$/;

function argumentsByName(values) {
  const result = new Map();
  for (let index = 0; index < values.length; index += 2) {
    const name = values[index];
    const value = values[index + 1];
    if (!name?.startsWith("--") || value === undefined || result.has(name)) {
      throw new Error("invalid CI artifact sanitizer arguments");
    }
    result.set(name, value);
  }
  return result;
}

function safeString(value, expression) {
  if (typeof value !== "string" || !expression.test(value)) {
    throw new Error("unsafe CI artifact field");
  }
  return value;
}

async function sanitizeLicenses(inputPath, outputPath) {
  const raw = JSON.parse(await readFile(inputPath, "utf8"));
  if (raw === null || Array.isArray(raw) || typeof raw !== "object") {
    throw new Error("invalid node license input");
  }

  const licenseGroups = Object.entries(raw)
    .map(([license, entries]) => {
      if (!Array.isArray(entries)) {
        throw new Error("invalid node license group");
      }
      const packages = entries
        .map((entry) => {
          if (
            entry === null ||
            typeof entry !== "object" ||
            Array.isArray(entry)
          ) {
            throw new Error("invalid node license entry");
          }
          const name = safeString(entry.name, PACKAGE_NAME);
          if (!Array.isArray(entry.versions)) {
            throw new Error("invalid node license versions");
          }
          return {
            name,
            versions: [
              ...new Set(
                entry.versions.map((version) => safeString(version, VERSION)),
              ),
            ].sort(),
          };
        })
        .sort((left, right) => left.name.localeCompare(right.name));
      return { license: safeString(license, LICENSE_TEXT), packages };
    })
    .sort((left, right) => left.license.localeCompare(right.license));

  await writeFile(
    outputPath,
    `${JSON.stringify({ schema_version: "mirror.ci.node-license-summary/v1", license_groups: licenseGroups }, null, 2)}\n`,
    "utf8",
  );
}

async function sanitizeDocker(inputPath, outputPath) {
  const rawText = await readFile(inputPath, "utf8");
  const trimmed = rawText.trim();
  let parsed;
  try {
    parsed = trimmed === "" ? [] : JSON.parse(trimmed);
  } catch {
    parsed = trimmed.split(/\r?\n/).map((line) => JSON.parse(line));
  }
  const records = Array.isArray(parsed) ? parsed : [parsed];
  const containers = records
    .map((entry) => {
      if (entry === null || typeof entry !== "object" || Array.isArray(entry)) {
        throw new Error("invalid compose status entry");
      }
      const exitCode = entry.ExitCode ?? entry.exitCode ?? 0;
      if (!Number.isInteger(exitCode) || exitCode < 0) {
        throw new Error("invalid compose exit code");
      }
      return {
        service: safeString(entry.Service ?? entry.service, SERVICE),
        state: safeString(entry.State ?? entry.state, STATE),
        health:
          entry.Health === undefined || entry.Health === ""
            ? null
            : safeString(entry.Health, STATE),
        exit_code: exitCode,
      };
    })
    .sort((left, right) => left.service.localeCompare(right.service));
  await writeFile(
    outputPath,
    `${JSON.stringify({ schema_version: "mirror.ci.compose-status/v1", containers }, null, 2)}\n`,
    "utf8",
  );
}

const options = argumentsByName(process.argv.slice(2));
const licensesInput = options.get("--licenses-input");
const licensesOutput = options.get("--licenses-output");
const dockerInput = options.get("--docker-input");
const dockerOutput = options.get("--docker-output");
if ((licensesInput === undefined) !== (licensesOutput === undefined)) {
  throw new Error("incomplete node license sanitizer arguments");
}
if ((dockerInput === undefined) !== (dockerOutput === undefined)) {
  throw new Error("incomplete compose sanitizer arguments");
}
if (licensesInput === undefined && dockerInput === undefined) {
  throw new Error("missing CI artifact sanitizer inputs");
}
if (licensesInput !== undefined && licensesOutput !== undefined) {
  await sanitizeLicenses(licensesInput, licensesOutput);
}
if (dockerInput !== undefined && dockerOutput !== undefined) {
  await sanitizeDocker(dockerInput, dockerOutput);
}
