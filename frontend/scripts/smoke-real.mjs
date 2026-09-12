// Requires a separate backend at 8001 seeded with DEV_USER_ID=frontend-smoke.
// This sends one real model request; it is deliberately outside the automatic test suite.
import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
const browser = await chromium.launch();
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    url.port = "8001";
    const response = await route.fetch({ url: url.href, timeout: 180000 });
    await route.fulfill({ response });
  });
  await page.goto("http://127.0.0.1:5173");
  await page.getByText("文字交流已连接").waitFor();
  const text = "这是页面联调测试。今天想和你聊一会儿，用一句简短的话回应我吧。";
  await page.getByRole("textbox", { name: "消息" }).fill(text);
  await page.getByRole("button", { name: "发送", exact: true }).click();
  await page.locator(".message.assistant").last().waitFor({ timeout: 180000 });
  await page.waitForFunction(() => !document.querySelector(".reply-wait"));
  assert.equal(await page.locator(".chat-error").count(), 0);
  const replies = await page
    .locator(".message.assistant .bubble")
    .allTextContents();
  assert(replies.at(-1)?.trim());
  await page.reload();
  await page.locator(".message.assistant").last().waitFor();
  assert.equal(
    await page.locator(".message.assistant .bubble").last().textContent(),
    replies.at(-1),
  );
  await mkdir("test-results", { recursive: true });
  await page.screenshot({ path: "test-results/real-chat.png" });
  for (const route of [
    "characters",
    "profile",
    "history",
    "settings",
    "memory",
  ]) {
    await page.goto(`http://127.0.0.1:5173/#/${route}/nanally`);
    await page.locator(".application").waitFor();
    await page.waitForTimeout(500);
    await page.screenshot({ path: `test-results/real-${route}.png` });
  }
  assert.deepEqual(errors, []);
  console.log(
    JSON.stringify({
      result: "passed",
      realReply: true,
      restoredAfterReload: true,
      pages: 6,
      browserErrors: errors.length,
    }),
  );
} finally {
  await browser.close();
}
