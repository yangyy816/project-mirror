import { cpSync, existsSync, mkdirSync } from "node:fs";
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
