import {
  cpSync,
  existsSync,
  mkdirSync,
  readdirSync,
  realpathSync,
} from "node:fs";
import { join } from "node:path";

const targetRoot = join(".next", "standalone", "apps", "web");
const targetNext = join(targetRoot, ".next");

mkdirSync(targetNext, { recursive: true });
cpSync(join(".next", "static"), join(targetNext, "static"), {
  recursive: true,
  force: true,
});

if (existsSync("public")) {
  cpSync("public", join(targetRoot, "public"), {
    recursive: true,
    force: true,
  });
}

// Next's pnpm standalone trace can leave @swc/helpers/esm unresolved on Linux.
// Mirror the production Docker assembly step without relying on shell globs.
const helperSource = join(
  "..",
  "..",
  "node_modules",
  ".pnpm",
  "node_modules",
  "@swc",
  "helpers",
  "esm",
);
const standaloneStore = join(".next", "standalone", "node_modules", ".pnpm");
const helperTargets = readdirSync(standaloneStore, { withFileTypes: true })
  .filter((entry) => entry.isDirectory() && entry.name.startsWith("next@"))
  .map((entry) =>
    join(standaloneStore, entry.name, "node_modules", "@swc", "helpers"),
  )
  .filter((path) => existsSync(path));

if (!existsSync(helperSource) || helperTargets.length === 0) {
  throw new Error("Unable to assemble Next standalone @swc/helpers runtime");
}

for (const helperTarget of helperTargets) {
  const helperDestination = join(helperTarget, "esm");
  if (
    existsSync(helperDestination) &&
    realpathSync(helperSource) === realpathSync(helperDestination)
  ) {
    continue;
  }

  cpSync(helperSource, helperDestination, {
    recursive: true,
    force: true,
  });
}
