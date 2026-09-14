import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import type { Memory, Session, Turn } from "../src/types";

type ApiOptions = {
  sessions?: Session[];
  turns?: Record<string, Turn[]>;
  memories?: Memory[];
  failHistoryPage?: boolean;
  delayConversation?: string;
  failConversationOnce?: string;
  delayMemoryInstance?: string;
  failMemoryInstance?: string;
  memory?: boolean;
};
const timestamp = "2026-09-12T12:30:00Z";
function session(id: string, version = id): Session {
  return {
    conversation_id: id,
    instance_id: `instance-${version}`,
    character_id: version.split("-")[0]!,
    name: "娜娜莉",
    version_id: version,
    checkpoint: "联调剧情起点",
    created_at: timestamp,
    last_activity_at: timestamp,
    turns: 0,
    preview: "",
  };
}
function turn(id: string, sequence: number, text: string): Turn {
  return {
    turn_id: id,
    request_id: `request-${id}`,
    sequence,
    status: "completed",
    error_code: null,
    created_at: timestamp,
    messages: [
      { message_id: `${id}-u`, role: "user", text },
      { message_id: `${id}-a`, role: "assistant", text: `收到：${text}` },
    ],
  };
}
async function fakeApi(
  page: Page,
  failFirst = false,
  options: ApiOptions = {},
) {
  const turns: Record<string, Turn[]> = options.turns || {};
  const sessions = new Map(
    (options.sessions || []).map((item) => [item.conversation_id, item]),
  );
  let failed = false;
  let historyFailed = false;
  let conversationFailed = false;
  const memories: Memory[] = [...(options.memories || [])];
  const requests: any[] = [];
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api", "");
    let body: unknown = {};
    if (path === "/health")
      body = {
        user_id: "browser-test",
        capabilities: { voice: false, memory: !!options.memory },
      };
    else if (path === "/sessions/open") {
      const id = route.request().postDataJSON().version_id;
      turns[id] ||= [];
      if (!sessions.has(id)) sessions.set(id, session(id));
      body = { conversation_id: id, instance_id: `instance-${id}` };
    } else if (path === "/history") {
      const offset = Number(url.searchParams.get("offset") || 0);
      const limit = Number(url.searchParams.get("limit") || 20);
      if (offset && options.failHistoryPage && !historyFailed) {
        historyFailed = true;
        await route.fulfill({
          status: 503,
          json: { error: "database_unavailable" },
        });
        return;
      }
      const items = [...sessions.values()]
        .filter(
          (item) => (turns[item.conversation_id]?.length || item.turns) > 0,
        )
        .map((item) => ({
          ...item,
          turns: turns[item.conversation_id]?.length || item.turns,
          preview:
            turns[item.conversation_id]?.at(-1)?.messages.at(-1)?.text ||
            item.preview,
        }));
      body = {
        items: items.slice(offset, offset + limit),
        total: items.length,
        offset,
        limit,
      };
    } else if (/^\/conversations\/[^/]+$/.test(path)) {
      const conversationId = decodeURIComponent(path.split("/")[2]!);
      if (
        conversationId === options.failConversationOnce &&
        !conversationFailed
      ) {
        conversationFailed = true;
        await route.fulfill({
          status: 503,
          json: { error: "database_unavailable" },
        });
        return;
      }
      body = sessions.get(conversationId);
      if (!body) {
        await route.fulfill({
          status: 404,
          json: { error: "conversation_not_found" },
        });
        return;
      }
    } else if (/^\/instances\/[^/]+\/memories$/.test(path)) {
      const instanceId = decodeURIComponent(path.split("/")[2]!);
      if (route.request().method() === "POST") {
        const input = route.request().postDataJSON();
        const existing = memories.find(
          (item) =>
            item.instance_id === instanceId &&
            item.source?.message_id === input.source_message_id,
        );
        if (existing) {
          await route.fulfill({
            status: 409,
            json: { error: "memory_source_already_saved" },
          });
          return;
        }
        let source: Memory["source"] = null;
        for (const [conversationId, items] of Object.entries(turns)) {
          for (const item of items) {
            if (
              item.messages.some(
                (message) => message.message_id === input.source_message_id,
              )
            )
              source = {
                message_id: input.source_message_id,
                turn_id: item.turn_id,
                conversation_id: conversationId,
                role: "user",
              };
          }
        }
        const memory: Memory = {
          memory_id: `memory-${memories.length + 1}`,
          instance_id: instanceId,
          kind: "fact",
          content: input.content,
          status: "active",
          revision: 1,
          created_at: timestamp,
          updated_at: timestamp,
          source,
        };
        memories.unshift(memory);
        body = memory;
      } else {
        if (instanceId === options.delayMemoryInstance)
          await new Promise((resolve) => setTimeout(resolve, 500));
        if (instanceId === options.failMemoryInstance) {
          await route.fulfill({
            status: 503,
            json: { error: "database_unavailable" },
          });
          return;
        }
        const offset = Number(url.searchParams.get("offset") || 0);
        const limit = Number(url.searchParams.get("limit") || 100);
        const matching = memories.filter(
          (item) => item.instance_id === instanceId,
        );
        body = {
          items: matching.slice(offset, offset + limit),
          total: matching.length,
          offset,
          limit,
        };
      }
    } else if (/^\/memories\/[^/]+$/.test(path)) {
      const memoryId = decodeURIComponent(path.split("/")[2]!);
      const index = memories.findIndex((item) => item.memory_id === memoryId);
      const item = memories[index]!;
      if (route.request().method() === "PATCH") {
        const input = route.request().postDataJSON();
        memories[index] = {
          ...item,
          content: input.content,
          revision: item.revision + 1,
        };
        body = memories[index];
      } else {
        memories.splice(index, 1);
        body = { ...item, content: null, status: "deleted" };
      }
    } else if (path.endsWith("/messages")) {
      const id = path.split("/")[2]!;
      turns[id] ||= [];
      if (route.request().method() === "POST") {
        const input = route.request().postDataJSON();
        requests.push({ ...input, conversation_id: id });
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
            error_code: null,
            created_at: timestamp,
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
        if (id === options.delayConversation)
          await new Promise((resolve) => setTimeout(resolve, 500));
        let offset = Number(url.searchParams.get("offset") || 0);
        const around = url.searchParams.get("around_turn_id");
        if (around)
          offset = Math.max(
            0,
            turns[id].findIndex((item) => item.turn_id === around) - 15,
          );
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

function memory(
  id: string,
  instanceId: string,
  content: string,
  updatedAt = timestamp,
): Memory {
  return {
    memory_id: id,
    instance_id: instanceId,
    kind: "fact",
    content,
    status: "active",
    revision: 1,
    created_at: updatedAt,
    updated_at: updatedAt,
    source: null,
  };
}

test("home is the default destination with four primary routes and continues into chat", async ({
  page,
}) => {
  await fakeApi(page);
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "今天，想和你相见。" }),
  ).toBeVisible();
  for (const name of ["首页", "角色", "回忆", "设置"])
    await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  await expect(page.locator(".last-meeting")).toContainText("娜娜莉");

  await page.getByRole("button", { name: "继续和 娜娜莉 聊天" }).click();
  await expect(page).toHaveURL(/#\/chat\/nanally/);
  await expect(page.getByRole("textbox", { name: "消息" })).toBeEnabled();
});

test("home recent cards use only the current conversation instance", async ({
  page,
}) => {
  const current = "nanally-integration-v1";
  await fakeApi(page, false, {
    memory: true,
    sessions: [session(current)],
    turns: { [current]: [turn("home-turn", 1, "今天一起看了雨")] },
    memories: [
      memory("current-memory", `instance-${current}`, "当前实例记得夜晚散步"),
      memory(
        "other-memory",
        "instance-iroi-integration-v1",
        "伊洛伊实例的秘密",
      ),
    ],
  });
  await page.goto("/");

  await expect(page.locator(".last-meeting")).toContainText("上次相见");
  await expect(page.locator(".recent-card")).toContainText([
    "当前实例记得夜晚散步",
    "今天一起看了雨",
  ]);
  await expect(page.getByText("伊洛伊实例的秘密", { exact: true })).toHaveCount(
    0,
  );
});

test("home clears old memories when a legacy instance or failed character instance is selected", async ({
  page,
}) => {
  const current = "nanally-integration-v1";
  const legacy = "legacy-chat";
  const legacySession = session(legacy, "nanally-legacy-v0");
  await fakeApi(page, false, {
    memory: true,
    sessions: [session(current), legacySession],
    turns: {
      [current]: [turn("current-home-turn", 1, "当前会话")],
      [legacy]: [turn("legacy-home-turn", 1, "旧实例会话")],
    },
    memories: [
      memory("current-memory", `instance-${current}`, "当前实例记忆"),
      memory("legacy-memory", legacySession.instance_id, "旧版本实例记忆"),
      memory(
        "iroi-memory",
        "instance-iroi-integration-v1",
        "不应泄露的伊洛伊记忆",
      ),
    ],
    failMemoryInstance: "instance-iroi-integration-v1",
  });
  await page.goto("/");
  await expect(page.getByText("当前实例记忆", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "回忆", exact: true }).click();
  await page.locator('.history-row[data-version="nanally-legacy-v0"]').click();
  await page.getByRole("button", { name: "首页", exact: true }).click();
  await expect(page.getByText("旧版本实例记忆", { exact: true })).toBeVisible();
  await expect(page.getByText("当前实例记忆", { exact: true })).toHaveCount(0);

  await page.goto("/#/home/iroi");
  await expect(page.locator(".home-state[role=alert]")).toContainText(
    "本地数据库",
  );
  await expect(page.getByText("旧版本实例记忆", { exact: true })).toHaveCount(
    0,
  );
  await expect(
    page.getByText("不应泄露的伊洛伊记忆", { exact: true }),
  ).toHaveCount(0);
});

test("chat survives refresh, isolates roles and resumes from history", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await fakeApi(page);
  await page.goto("/#/chat/nanally");
  await expect(page.getByText("在这里", { exact: true })).toBeVisible();
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
  await page.getByRole("button", { name: "回忆", exact: true }).click();
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
  await page.goto("/#/chat/nanally");
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
  await page.goto("/#/chat/nanally");
  await expect(page.getByRole("alert")).toContainText("本地数据库");
  await expect(page.getByRole("textbox", { name: "消息" })).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "发送", exact: true }),
  ).toBeDisabled();
  await expect(page.locator(".message.assistant")).toHaveCount(0);
});

test("personal memories are explicitly saved, corrected, linked, and deleted", async ({
  page,
}) => {
  await fakeApi(page, false, { memory: true });
  await page.goto("/#/chat/nanally");
  const input = page.getByRole("textbox", { name: "消息" });
  await input.fill("我喜欢在雨天散步");
  await page.getByRole("button", { name: "发送", exact: true }).click();
  await page.getByRole("button", { name: "记住这件事" }).click();
  await expect(page).toHaveURL(/#\/memory\/nanally/);
  await expect(page.getByLabel("希望她记住什么？")).toHaveValue(
    "我喜欢在雨天散步",
  );
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(
    page.getByText("我喜欢在雨天散步", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "更正" }).click();
  await page.getByLabel("更正记忆内容").fill("我喜欢在小雨的夜晚散步");
  await page.getByRole("button", { name: "保存更正" }).click();
  await expect(
    page.getByText("我喜欢在小雨的夜晚散步", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "查看来源" }).click();
  await expect(page.locator(".source-turn")).toContainText("我喜欢在雨天散步");
  await page.goto("/#/memory/nanally");
  await page.getByRole("button", { name: "删除" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "确认删除" })
    .click();
  await expect(
    page.getByRole("heading", { name: "还没有保存的记忆" }),
  ).toBeVisible();
});

test("legacy versions restore their metadata and keep drafts and outbox in their own conversation", async ({
  page,
}) => {
  const current = "nanally-integration-v1";
  const legacy = {
    ...session("legacy-chat", "nanally-legacy-v0"),
    checkpoint: "旧剧情第二章",
    created_at: null,
    last_activity_at: null,
  };
  const legacyTurn = {
    ...turn("legacy-turn", 1, "旧版本里的问候"),
    created_at: null,
  };
  const requests = await fakeApi(page, true, {
    sessions: [session(current), legacy],
    turns: {
      [current]: [turn("current-turn", 1, "当前版本的开场")],
      "legacy-chat": [legacyTurn],
    },
  });
  await page.goto("/#/chat/nanally");
  const input = page.getByRole("textbox", { name: "消息" });
  await input.fill("只属于当前会话的待发消息");
  await page.getByRole("button", { name: "发送", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("暂时没有收到回复");
  await input.fill("当前草稿也要保留");
  await page.getByRole("button", { name: "回忆", exact: true }).click();
  await page.locator('.history-row[data-version="nanally-legacy-v0"]').click();
  await expect(page.getByText("旧版本里的问候", { exact: true })).toBeVisible();
  await expect(input).toHaveValue("");
  await expect(
    page.getByText("只属于当前会话的待发消息", { exact: true }),
  ).toHaveCount(0);
  await expect(page.locator(".chat-workspace")).toHaveAttribute(
    "data-version",
    "nanally-legacy-v0",
  );
  await expect(page.locator(".turn-time")).toHaveText("未记录时间");
  await expect(page.locator(".application")).toHaveCSS("--accent", "#cf3979");
  await input.fill("旧版本草稿");
  await page.reload();
  await expect(input).toHaveValue("旧版本草稿");
  await expect(page.locator(".chat-workspace")).toHaveAttribute(
    "data-version",
    "nanally-legacy-v0",
  );
  await page.getByRole("button", { name: "发送", exact: true }).click();
  await expect(
    page.getByText("收到：旧版本草稿", { exact: true }),
  ).toBeVisible();
  expect(requests[1].conversation_id).toBe("legacy-chat");
  await page.getByRole("button", { name: "角色资料", exact: true }).click();
  await expect(
    page.locator(".metadata-row").filter({ hasText: "剧情进度" }),
  ).toContainText("旧剧情第二章");
  await expect(
    page.locator(".metadata-row").filter({ hasText: "会话版本" }),
  ).toContainText("nanally-legacy-v0");
  await page.getByRole("button", { name: "回忆", exact: true }).click();
  await page.locator(`.history-row[data-version="${current}"]`).click();
  await expect(input).toHaveValue("当前草稿也要保留");
  await expect(page.getByRole("alert")).toContainText("尚未完成");
  await page.getByRole("button", { name: "重试", exact: true }).click();
  await expect(
    page.getByText("收到：只属于当前会话的待发消息", { exact: true }),
  ).toBeVisible();
  expect(requests[2].request_id).toBe(requests[0].request_id);
  expect(requests[2].conversation_id).toBe(current);
});

test("history pagination failure retains loaded rows and retries the same page", async ({
  page,
}) => {
  const sessions = Array.from({ length: 21 }, (_, i) => ({
    ...session(`history-${i}`, "nanally-integration-v1"),
    turns: 1,
    preview: `第 ${i + 1} 段历史`,
    last_activity_at: i === 0 ? null : timestamp,
  }));
  await fakeApi(page, false, { sessions, failHistoryPage: true });
  await page.goto("/#/history/nanally");
  await expect(page.locator(".history-row")).toHaveCount(20);
  await expect(page.locator(".history-row").first()).toContainText(
    "未记录时间",
  );
  await expect(page.locator(".history-row time").nth(1)).toHaveAttribute(
    "datetime",
    timestamp,
  );
  await page.getByRole("button", { name: "加载更多对话" }).click();
  await expect(page.getByRole("alert")).toContainText("本地数据库");
  await expect(page.locator(".history-row")).toHaveCount(20);
  await page.getByRole("button", { name: "重新加载", exact: true }).click();
  await expect(page.locator(".history-row")).toHaveCount(21);
  await expect(page.locator(".history-row").last()).toContainText(
    "第 21 段历史",
  );
  await expect(page.getByRole("button", { name: "加载更多对话" })).toHaveCount(
    0,
  );
});

test("conversation and turn links locate the exact source outside the latest message page", async ({
  page,
}) => {
  const id = "source-chat";
  await fakeApi(page, false, {
    sessions: [session(id, "nanally-legacy-v0")],
    turns: {
      [id]: Array.from({ length: 95 }, (_, i) =>
        turn(`source-${i + 1}`, i + 1, `来源对话 ${i + 1}`),
      ),
    },
  });
  await page.goto("/#/chat/nanally?conversation=source-chat&turn=source-40");
  await expect(page.locator(".source-turn")).toHaveAttribute(
    "data-turn-id",
    "source-40",
  );
  await expect(page.locator(".source-turn")).toBeInViewport();
  await expect(page.getByText("来源对话 95", { exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.locator(".source-turn")).toBeInViewport();
  await page.getByRole("button", { name: "返回最新对话" }).click();
  await expect(page.getByText("来源对话 95", { exact: true })).toBeVisible();
  await expect(page).not.toHaveURL(/&turn=/);
});

test("late legacy history responses cannot replace the newly selected conversation", async ({
  page,
}) => {
  const current = "nanally-integration-v1";
  await fakeApi(page, false, {
    sessions: [session(current), session("slow-chat", "nanally-legacy-v0")],
    turns: {
      [current]: [turn("fast-turn", 1, "当前会话保持不变")],
      "slow-chat": [turn("slow-turn", 1, "较慢的旧会话")],
    },
    delayConversation: "slow-chat",
  });
  await page.goto("/#/chat/nanally?conversation=slow-chat");
  await page.waitForRequest((request) =>
    request.url().includes("slow-chat/messages"),
  );
  await page.getByRole("button", { name: "回忆", exact: true }).click();
  await page.locator(`.history-row[data-version="${current}"]`).click();
  await expect(
    page.getByText("当前会话保持不变", { exact: true }),
  ).toBeVisible();
  await page.waitForResponse(
    (response) =>
      response.url().includes("slow-chat/messages") &&
      response.url().includes("limit=30"),
  );
  await expect(page.getByText("较慢的旧会话", { exact: true })).toHaveCount(0);
  await expect(page.locator(".chat-workspace")).toHaveAttribute(
    "data-version",
    current,
  );
});

test("pending message reloads failed conversation metadata before retrying", async ({
  page,
}) => {
  const id = "pending-chat";
  const requests = await fakeApi(page, false, {
    sessions: [session(id, "nanally-integration-v1")],
    failConversationOnce: id,
  });
  await page.addInitScript(
    ({ key, value }) => {
      localStorage.setItem(key, JSON.stringify(value));
    },
    {
      key: "afterstory:browser-test:draft:nanally",
      value: {
        id,
        draft: "",
        pending: { request_id: "pending-request", text: "保留下来的消息" },
      },
    },
  );
  await page.goto(`/#/chat/nanally?conversation=${id}`);
  await expect(page.getByRole("alert")).toBeVisible();
  await page.getByRole("button", { name: "重试", exact: true }).click();
  await expect(
    page.getByText("收到：保留下来的消息", { exact: true }),
  ).toBeVisible();
  expect(
    requests.filter((request) => request.request_id === "pending-request"),
  ).toHaveLength(1);
});

test("character selection expands beyond the initial cast without overflow or hover switching", async ({
  page,
}) => {
  await fakeApi(page);
  await page.route("**/characters.json", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    for (let i = 0; i < 5; i++)
      data.characters.push({
        ...data.characters[0],
        id: `guest-${i}`,
        name: `访客${i}`,
        default: false,
      });
    await route.fulfill({ json: data });
  });
  await page.goto("/#/characters/nanally");
  await expect(page.locator(".character-panel")).toHaveCount(8);
  const featured = page.locator(".character-panel.featured");
  const featuredBox = await featured.boundingBox();
  const actionBox = await featured.locator(".visit-action").boundingBox();
  expect(actionBox!.y + actionBox!.height).toBeLessThan(
    featuredBox!.y + featuredBox!.height,
  );
  await page.locator(".character-panel").filter({ hasText: "伊洛伊" }).hover();
  await expect(page.locator(".application")).toHaveCSS("--accent", "#cf3979");
  for (const width of [1440, 900]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: "test-results/characters-expanded.png",
    fullPage: true,
  });
});

test("immersive chat keeps send preferences, multiline text and older-message reading position", async ({
  page,
}) => {
  const id = "nanally-integration-v1";
  const requests = await fakeApi(page, false, {
    sessions: [session(id)],
    turns: {
      [id]: Array.from({ length: 65 }, (_, i) =>
        turn(`read-${i + 1}`, i + 1, `读过的片段 ${i + 1}`),
      ),
    },
  });
  await page.goto("/#/chat/nanally");
  const chat = page.locator(".chat-workspace");
  await expect(chat).not.toContainText("integration-v1");
  await expect(chat).not.toContainText("文字交流已连接");
  await expect(chat).not.toContainText("联调");
  const input = page.getByRole("textbox", { name: "消息" });
  await expect(input).toHaveAttribute("placeholder", "想和娜娜莉说些什么……");
  await page.locator(".messages").evaluate((el) => {
    el.scrollTop = 0;
  });
  await page.getByRole("button", { name: "查看更早的对话" }).click();
  await expect(page.getByText("读过的片段 6", { exact: true })).toBeAttached();
  expect(
    await page.locator(".messages").evaluate((el) => el.scrollTop),
  ).toBeGreaterThan(0);
  await page.getByRole("button", { name: "设置", exact: true }).click();
  await page.getByLabel("发送方式").selectOption("ctrl");
  await page.getByRole("button", { name: "返回聊天", exact: true }).click();
  await input.fill("第一行");
  await input.press("Shift+Enter");
  await input.press("a");
  expect(requests).toHaveLength(0);
  await input.press("Enter");
  expect(requests).toHaveLength(0);
  await input.press("Control+Enter");
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0].text).toContain("第一行\na");
  await expect(page.locator(".messages")).toContainText("收到：第一行");
  expect(
    await page
      .locator(".messages")
      .evaluate((el) => el.scrollHeight - el.clientHeight - el.scrollTop),
  ).toBeLessThan(30);
});

test("memory filters load later pages and keep facts separate from conversation excerpts", async ({
  page,
}) => {
  const id = "nanally-integration-v1";
  await fakeApi(page, false, {
    memory: true,
    sessions: [session(id)],
    memories: Array.from({ length: 101 }, (_, i) =>
      memory(
        `memory-${i}`,
        `instance-${id}`,
        i === 100 ? "最后一页的特别记忆" : `平常的记忆 ${i}`,
      ),
    ),
  });
  await page.goto("/#/memory/nanally");
  await expect(
    page.getByRole("heading", { name: "与你的回忆", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("tab", { name: /她记得的事/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.getByRole("searchbox", { name: "搜索回忆" }).fill("最后一页");
  await expect(page.locator(".memory-list article")).toHaveCount(1);
  await expect(page.locator(".memory-list article")).toContainText(
    "最后一页的特别记忆",
  );
});

test("memory requests that finish after a role switch cannot populate the new role", async ({
  page,
}) => {
  await fakeApi(page, false, {
    memory: true,
    delayMemoryInstance: "instance-nanally-integration-v1",
    memories: [
      memory(
        "slow",
        "instance-nanally-integration-v1",
        "不能出现在伊洛伊的内容",
      ),
      memory("fast", "instance-iroi-integration-v1", "伊洛伊记得的内容"),
    ],
  });
  await page.goto("/#/memory/nanally");
  await page.waitForRequest((request) =>
    request.url().includes("instance-nanally-integration-v1/memories"),
  );
  await page.evaluate(() => {
    location.hash = "#/memory/iroi";
  });
  await expect(page.locator(".memory-list")).toContainText("伊洛伊记得的内容");
  await page.waitForTimeout(650);
  await expect(page.locator(".memory-list")).not.toContainText(
    "不能出现在伊洛伊的内容",
  );
});

test("history filters find a matching role on later pages while retaining unknown dates", async ({
  page,
}) => {
  const sessions = Array.from({ length: 21 }, (_, i) => ({
    ...session(
      `filter-${i}`,
      i === 20 ? "iroi-integration-v1" : "nanally-integration-v1",
    ),
    turns: 1,
    preview: i === 20 ? "伊洛伊的雨天" : "娜娜莉的日常",
    last_activity_at: null,
  }));
  await fakeApi(page, false, { sessions });
  await page.goto("/#/history/nanally");
  await expect(page.locator(".history-row")).toHaveCount(20);
  await page.getByLabel("筛选角色").selectOption("iroi");
  await expect(page.locator(".history-row")).toHaveCount(1);
  await expect(page.locator(".history-row")).toContainText("伊洛伊的雨天");
  await expect(page.locator(".history-row")).toContainText("未记录时间");
  await expect(page.locator(".history-row")).not.toContainText(
    "integration-v1",
  );
});
