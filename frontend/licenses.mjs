import fs from "node:fs";
import path from "node:path";
const parts = [
  "BrainFC: bundled client dependencies.\nHyper-Brain source adaptation: Apache-2.0; see root LICENSE and NOTICE.",
];
for (const name of ["react", "react-dom", "scheduler", "three"]) {
  const root = path.resolve("node_modules", name),
    pkg = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
  parts.push(
    `\n===== ${name} ${pkg.version} =====\n` +
      fs.readFileSync(path.join(root, "LICENSE"), "utf8"),
  );
}
fs.writeFileSync(
  "../src/brainfc/web/static/THIRD_PARTY_NOTICES.txt",
  parts.join("\n"),
);
