import { mkdir, copyFile, access } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../", import.meta.url));
const output = path.join(root, "public/media");
await mkdir(output, { recursive: true });
for (const [name, fallback] of [
  ["nanally", "nanally-official-introduction.jpg"],
  ["iroi", "iroi-official-banner.jpeg"],
  ["mint", "mint-official-introduction.jpg"],
]) {
  const selected = path.resolve(
    root,
    "../data/character-assets",
    `${name}.png`,
  );
  const original = path.resolve(root, "../data/design-reference", fallback);
  let source = selected;
  try {
    await access(source);
  } catch {
    source = original;
  }
  try {
    await copyFile(source, path.join(output, `${name}.image`));
  } catch {
    console.warn(
      `角色图片缺失：${name}。请在 data/character-assets/ 放入 ${name}.png，或通过页面更换封面。`,
    );
  }
}
