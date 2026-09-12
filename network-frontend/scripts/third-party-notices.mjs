// Reproduce release notices solely from installed locked packages and checked-in licenses.
import { readFile, writeFile, readdir, stat, mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import { createHash } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../", import.meta.url));
const lock = JSON.parse(
  await readFile(path.join(root, "package-lock.json"), "utf8"),
);
const sources = JSON.parse(
  await readFile(path.join(root, "licenses/sources.json"), "utf8"),
);
const hash = (text) => createHash("sha256").update(text).digest("hex");
const sections = [];
const add = (title, body) =>
  sections.push(
    `${"=".repeat(78)}\n${title}\n${"=".repeat(78)}\n\n${body.trim()}\n`,
  );
const inventory = [];
const excluded = [];
for (const [relative, entry] of Object.entries(lock.packages).sort(([a], [b]) =>
  a.localeCompare(b),
)) {
  if (!relative || entry.dev) continue;
  // NiiVue declares this compiler binary optional; it is never a browser asset.
  if (relative.includes("node_modules/@rollup/rollup-")) {
    excluded.push(
      `${relative}: optional native build binary, not bundled in the browser`,
    );
    continue;
  }
  const folder = path.join(root, relative);
  if (!existsSync(folder))
    throw new Error(
      `Required runtime package missing: ${relative}; run npm ci.`,
    );
  const pkg = JSON.parse(
    await readFile(path.join(folder, "package.json"), "utf8"),
  );
  if (entry.version !== pkg.version)
    throw new Error(`Installed/lock version mismatch: ${relative}`);
  if (!entry.license || entry.license !== pkg.license)
    throw new Error(
      `Installed/lock SPDX mismatch: ${relative}: ${entry.license} vs ${pkg.license}`,
    );
  const licenseFiles = (await readdir(folder))
    .filter((file) => /^(licen[sc]e|copying|notice)(\..*)?$/i.test(file))
    .sort();
  let texts = [];
  for (const file of licenseFiles) {
    const target = path.join(folder, file);
    if ((await stat(target)).isFile())
      texts.push({ name: file, text: await readFile(target, "utf8") });
  }
  if (
    !texts.length &&
    pkg.name === "@niivue/niivue" &&
    pkg.version === "0.67.0"
  )
    texts = [
      {
        name: "upstream LICENSE at npm gitHead 7021c439133ea9f63836f48cbdbbddea26e411ef",
        text: await readFile(
          path.join(root, "licenses/niivue-0.67.0.txt"),
          "utf8",
        ),
      },
    ];
  if (!texts.length)
    throw new Error(`Full license text missing: ${pkg.name}@${pkg.version}`);
  inventory.push(
    `${pkg.name}@${pkg.version} | declared SPDX: ${entry.license} | ${relative}`,
  );
  const repository =
    typeof pkg.repository === "string" ? pkg.repository : pkg.repository?.url;
  add(
    `${pkg.name}@${pkg.version} — ${entry.license}`,
    `Source package: ${relative}\nRegistry integrity: ${entry.integrity || "not recorded"}\nRepository: ${repository || pkg.homepage || "see npm package metadata"}\n\n` +
      texts
        .map(
          ({ name, text }) =>
            `License source: ${name}\nSHA-256: ${hash(text)}\n\n${text}`,
        )
        .join("\n\n"),
  );
}
const unique = new Set();
// Preserve original author-attributed license blocks in NiiVue's vendored utilities.
for (const relative of [
  "src/nvmesh-utilities.ts",
  "src/nvutilities.ts",
  "src/nvimage/utils.ts",
]) {
  const text = await readFile(
    path.join(root, "node_modules/@niivue/niivue", relative),
    "utf8",
  );
  for (const [comment] of text.matchAll(/\/\*[\s\S]*?\*\//g)) {
    if (
      comment.length < 20000 &&
      /copyright/i.test(comment) &&
      /permission|redistribution/i.test(comment) &&
      !unique.has(comment)
    ) {
      unique.add(comment);
      add(`NiiVue embedded attribution — ${relative}`, comment);
    }
  }
}
const plotly = await readFile(
  path.join(root, "node_modules/plotly.js-dist-min/plotly.min.js"),
  "utf8",
);
for (const [comment] of plotly.matchAll(/\/\*![\s\S]*?\*\//g)) {
  if (
    comment.length < 30000 &&
    /license|copyright/i.test(comment) &&
    !unique.has(comment)
  ) {
    unique.add(comment);
    add("Plotly upstream bundled attribution (preserved verbatim)", comment);
  }
}
for (const source of sources) {
  const text = await readFile(path.join(root, "licenses", source.file), "utf8");
  if (!source.sha256 || hash(text) !== source.sha256)
    throw new Error(`Supplemental license hash mismatch: ${source.file}`);
  if (source.file === "niivue-0.67.0.txt") continue; // full text is already in package inventory.
  add(
    `${source.name} — ${source.spdx}`,
    `Source: ${source.url}\nSHA-256: ${source.sha256}\n${source.note || ""}\n\n${text}`,
  );
}
add(
  "Additional Apache-2.0 attributions retained from NiiVue",
  "Steve Pieper 2022: Apache License 2.0 (src/shader-srcs.ts).\nRoboto font: Copyright Google / the Roboto contributors; NiiVue packages a rendered Roboto-Regular glyph atlas.\nFastSurfer attribution and Apache-2.0 license text are reproduced above.",
);
const header = `HIC-Brain bundled frontend — third-party notices\n\nGenerated by frontend/scripts/third-party-notices.mjs from package-lock.json.\nLock SHA-256: ${hash(await readFile(path.join(root, "package-lock.json")))}\n\nHIC-Brain original source is Apache-2.0. External code retains its own license.\nThe inventory conservatively includes every installed non-dev runtime package;\ntree-shaking can omit parts of these packages. Build-only tools are not bundled.\nPrebundled Plotly/NiiVue/WASM components retain supplemental upstream notices below.\nNo patient data, local upload, or node_modules directory is included in this file.\nThis file is regenerated after every production build without network access.\n\nRuntime package inventory (${inventory.length}):\n${inventory.join("\n")}\n\nExcluded build-only lock entries:\n${excluded.join("\n")}\n\n`;
const output = path.join(
  root,
  "../src/brainfc/network/web/static/THIRD_PARTY_NOTICES.txt",
);
await mkdir(path.dirname(output), { recursive: true });
await writeFile(output, header + sections.join("\n"), "utf8");
console.log(
  `Third-party notices: ${inventory.length} runtime packages, ${sources.length} supplemental license sources; SPDX and source hashes verified.`,
);
