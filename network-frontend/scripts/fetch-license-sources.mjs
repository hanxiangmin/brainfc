// Maintainer-only refresh. Normal builds are offline and never invoke this file.
import { readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
const base = new URL("../licenses/", import.meta.url);
const sources = JSON.parse(
  await readFile(new URL("sources.json", base), "utf8"),
);
for (let start = 0; start < sources.length; start += 3) {
  await Promise.all(
    sources.slice(start, start + 3).map(async (source) => {
      const response = await fetch(source.url, {
        signal: AbortSignal.timeout(30000),
      });
      if (!response.ok)
        throw new Error(`${source.name}: HTTP ${response.status}`);
      let text = (await response.text()).replaceAll("\r\n", "\n");
      if (source.headerOnly)
        text = text.split("\n").slice(0, 13).join("\n") + "\n";
      if (!/license|permission|redistribution/i.test(text))
        throw new Error(`No license terms found: ${source.name}`);
      await writeFile(new URL(source.file, base), text);
      source.sha256 = createHash("sha256").update(text).digest("hex");
      console.log(`Saved ${source.file}`);
    }),
  );
}
await writeFile(
  new URL("sources.json", base),
  JSON.stringify(sources, null, 2) + "\n",
);
