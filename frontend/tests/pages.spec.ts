import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";

async function fakeApi(page: Page, failFirst = false) {
  const turns: Record<string, any[]> = {};
  let failed = false;
  const requests: any[] = [];
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api", "");
    let body: unknown = {};
    if (path === "/health")
      body = {
        user_id: "browser-test",
        capabilities: { voice: false, memory: false },
      };
    else if (path === "/sessions/open") {
      const id = route.request().postDataJSON().version_id;
      turns[id] ||= [];
      body = { conversation_id: id };
    } else if (path === "/conversations")
      body = Object.entries(turns)
        .filter(([, value]) => value.length)
        .map(([id, value]) => ({
          conversation_id: id,
          version_id: id,
          turns: value.length,
          preview: value.at(-1).messages.at(-1).text,
        }));
    else if (path.endsWith("/messages")) {
      const id = path.split("/")[2]!;
      turns[id] ||= [];
      if (route.request().method() === "POST") {
        const input = route.request().postDataJSON();
        requests.push(input);
        if (failFirst && !failed) {
          failed = true;
          await route.fulfill({
            status: 503,
            json: { error: "provider_unavailable" },
          });
          return;
        }
        if (!turns[id].some((t) => t.request_id === input.request_id))
          turns[id].push({
            turn_id: input.request_id,
            request_id: input.request_id,
            sequence: turns[id].length + 1,
            status: "completed",
            messages: [
              {
                message_id: input.request_id + "u",
                role: "user",
                text: input.text,
              },
              {
                message_id: input.request_id + "a",
                role: "assistant",
                text: "收到：" + input.text,
              },
            ],
          });
        body = { text: "收到：" + input.text };
      } else {
        const offset = Number(url.searchParams.get("offset") || 0);
        body = {
          total: turns[id].length,
          offset,
          turns: turns[id].slice(
            offset,
            offset + Number(url.searchParams.get("limit") || 20),
          ),
        };
      }
    }
    await route.fulfill({ json: body });
  });
  return requests;
}

test("chat survives refresh, isolates roles and resumes from history", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await fakeApi(page);
  await page.goto("/");
  await expect(page.getByText("文字交流已连接")).toBeVisible();
  await page.getByRole("textbox", { name: "消息" }).fill("今天下雨了");
  await page.getByRole("button", { name: "发送", exact: true }).click();
  await expect(
    page.getByText("收到：今天下雨了", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("收到：今天下雨了", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "角色", exact: true }).click();
  await page.locator(".character-panel").filter({ hasText: "伊洛伊" }).hover();
  await expect(page.locator(".application")).toHaveCSS("--accent", "#cf3979");
  await page.locator(".character-panel").filter({ hasText: "伊洛伊" }).click();
  await expect(page.locator(".application")).toHaveCSS("--accent", "#507c68");
  await expect(page.getByText("今天下雨了", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "历史", exact: true }).click();
  await page.locator(".history-row").click();
  await expect(
    page.getByText("收到：今天下雨了", { exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
  await page.screenshot({ path: "test-results/chat-desktop.png" });
});

test("IME does not send, failed outbox retries same request after refresh", async ({
  page,
}) => {
  const requests = await fakeApi(page, true);
  await page.goto("/");
  const input = page.getByRole("textbox", { name: "消息" });
  await expect(input).toBeEnabled();
  await input.fill("你好");
  await input.dispatchEvent("keydown", { key: "Enter", isComposing: true });
  expect(requests).toHaveLength(0);
  await input.press("Enter");
  await expect(page.getByRole("alert")).toContainText("暂时没有收到回复");
  await page.reload();
  await expect(page.getByRole("alert")).toContainText("尚未完成");
  await page.getByRole("button", { name: "重试", exact: true }).click();
  await expect(page.getByText("收到：你好", { exact: true })).toBeVisible();
  expect(requests).toHaveLength(2);
  expect(requests[0].request_id).toEqual(requests[1].request_id);
  await expect(page.locator(".message.user")).toHaveCount(1);
});

test("cover edits cancel, persist, isolate and reset; settings and capability states", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await fakeApi(page);
  await page.goto("/#/settings/nanally");
  await expect(
    page.getByRole("button", { name: "外观", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "大", exact: true }).click();
  await page.getByRole("button", { name: "外观", exact: true }).click();
  await page
    .getByRole("button", { name: "更换封面", exact: true })
    .last()
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("左右位置").fill("80");
  await dialog
    .locator("input[type=file]")
    .setInputFiles("../data/character-assets/iroi.png");
  await expect(dialog.locator(".portrait img").first()).toHaveAttribute(
    "src",
    /^data:image\/png;base64,/,
  );
  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  await page.getByRole("button", { name: "调整位置" }).click();
  await expect(dialog.getByLabel("左右位置")).toHaveValue("48");
  await dialog.getByLabel("左右位置").fill("80");
  await dialog.getByRole("button", { name: "保存封面" }).click();
  await expect(dialog).toHaveCount(0);
  await page.reload();
  await expect(page.locator(".application")).toHaveClass(/font-large/);
  await page.getByRole("button", { name: "外观", exact: true }).click();
  await page.getByRole("button", { name: "调整位置" }).click();
  await expect(dialog.getByLabel("左右位置")).toHaveValue("80");
  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  await page.getByRole("button", { name: "恢复默认", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "恢复默认", exact: true })
    .click();
  await page.getByRole("button", { name: "声音", exact: true }).click();
  await expect(page.getByText("语音尚未启用", { exact: true })).toBeVisible();
  await expect(page.getByLabel("语音播放方式")).toHaveValue("manual");
  await page.getByRole("button", { name: "数据管理", exact: true }).click();
  await page.getByRole("button", { name: /个人记忆/ }).click();
  await expect(
    page.getByRole("heading", { name: "个人记忆还未启用" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("offline backend shows an honest retry state", async ({ page }) => {
  await page.route("**/api/**", (route) =>
    route.fulfill({ status: 503, json: { error: "database_unavailable" } }),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("本地数据库");
  await expect(page.getByRole("textbox", { name: "消息" })).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "发送", exact: true }),
  ).toBeDisabled();
  await expect(page.locator(".message.assistant")).toHaveCount(0);
});
