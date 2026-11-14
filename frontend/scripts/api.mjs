// The dashboard's API types, generated from the backend's OpenAPI document.
//
//   npm run api:gen     writes src/api/schema.d.ts
//   npm run api:check   exits with 1 when src/api/schema.d.ts is not what the
//                       backend generates now (a model changed without api:gen)
//
// The schema comes from `uv run python -m openings.openapi` (no server is
// started) and is turned into types by openapi-typescript, which runs from its
// own folder (tools/openapi) because it needs TypeScript 5 and the dashboard
// builds with TypeScript 7. The intermediate openapi.json is not kept.
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import * as prettier from "prettier";

const frontend = fileURLToPath(new URL("..", import.meta.url));
const tools = new URL("../tools/openapi/", import.meta.url);
const target = new URL("../src/api/schema.d.ts", import.meta.url);
const check = process.argv.includes("--check");

if (!existsSync(new URL("node_modules/openapi-typescript", tools)))
  execFileSync("npm", ["ci", "--silent", "--no-audit", "--no-fund"], {
    cwd: fileURLToPath(tools),
    stdio: "inherit",
  });
const { default: openapiTS, astToString } = await import(
  pathToFileURL(
    fileURLToPath(
      new URL("node_modules/openapi-typescript/dist/index.mjs", tools),
    ),
  ).href
);

const schema = JSON.parse(
  execFileSync(
    "uv",
    ["run", "--project", "..", "python", "-m", "openings.openapi"],
    {
      cwd: frontend,
      encoding: "utf8",
      maxBuffer: 64 * 1024 * 1024,
    },
  ),
);
// The version changes with every release, not with the contract.
schema.info.version = "current";
const header =
  "// Generated from the backend's OpenAPI document by `npm run api:gen`.\n" +
  "// Do not edit: change the backend models and run `npm run api:gen` again.\n\n";
const types = await prettier.format(
  header + astToString(await openapiTS(schema, { alphabetize: true })),
  { parser: "typescript", filepath: fileURLToPath(target) },
);

if (!check) {
  writeFileSync(target, types);
  console.log(`Wrote ${fileURLToPath(target)}.`);
} else if (!existsSync(target) || readFileSync(target, "utf8") !== types) {
  console.error(
    "src/api/schema.d.ts differs from the backend's OpenAPI document. " +
      "Run `npm --prefix frontend run api:gen` and commit the result.",
  );
  process.exit(1);
} else {
  console.log("src/api/schema.d.ts matches the backend's OpenAPI document.");
}
