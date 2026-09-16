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

test("home encounter hero follows three characters across desktop viewports and retains actions", async ({
  page,
}) => {
  test.setTimeout(60000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const id = "nanally-integration-v1";
  await fakeApi(page, false, {
    memory: true,
    sessions: [session(id)],
    turns: {
      [id]: [
        turn("home-encounter-turn", 1, "最近工作有点多，脑子都转不动了。"),
      ],
    },
    memories: [
      memory(
        "home-encounter-memory",
        `instance-${id}`,
        "你最近正在忙一个自己的项目。",
      ),
    ],
  });
  const characters = [
    {
      id: "nanally",
      name: "娜娜莉",
      greeting: "哼，今天也回来啦。",
      accent: "#cf3979",
    },
    {
      id: "iroi",
      name: "伊洛伊",
      greeting: "你来了呀……今天也一起待一会儿吧。",
      accent: "#507c68",
    },
    {
      id: "mint",
      name: "薄荷",
      greeting: "抓到你啦！今天有什么新鲜事？",
      accent: "#167e88",
    },
  ];
  for (const [width, height] of [
    [1920, 1080],
    [1600, 900],
    [1440, 900],
    [1366, 768],
  ]) {
    await page.setViewportSize({ width, height });
    for (const c of characters) {
      await page.goto(`/#/home/${c.id}`);
      await expect(page.locator(".home-greeting")).toHaveText(c.greeting);
      await expect(page.locator(".application")).toHaveCSS(
        "--accent",
        c.accent,
      );
      await expect(page.locator(".home-art img")).toHaveAttribute(
        "src",
        `/media/${c.id}-scene.png`,
      );
      await expect(page.locator(".home-art img")).toHaveJSProperty(
        "naturalWidth",
        1672,
      );
      await expect(page.locator(".home-page .glass-panel")).toHaveCount(0);
      const composition = await page.locator(".home-page").evaluate((root) => {
        const hero = root.querySelector(".home-hero")!.getBoundingClientRect();
        const secondary = root
          .querySelector(".home-middle")!
          .getBoundingClientRect();
        const greeting = root
          .querySelector(".home-greeting")!
          .getBoundingClientRect();
        const welcome = root
          .querySelector(".home-welcome")!
          .getBoundingClientRect();
        return {
          viewportLocked:
            document.documentElement.scrollHeight <= innerHeight &&
            document.documentElement.scrollWidth <= innerWidth,
          heroDominates: hero.height > secondary.height * 1.3,
          greetingFits:
            greeting.top >= welcome.top &&
            greeting.bottom <= welcome.bottom + 1 &&
            welcome.top >= hero.top &&
            welcome.bottom <= hero.bottom + 1,
          header: document.querySelector(".topbar")!.getBoundingClientRect()
            .height,
        };
      });
      expect(composition).toEqual({
        viewportLocked: true,
        heroDominates: true,
        greetingFits: true,
        header: 72,
      });
      if (c.id !== "nanally") {
        await expect(
          page.getByText("第一段回忆，还在等你们写下。", { exact: true }),
        ).toBeVisible();
        await expect(
          page.getByRole("button", { name: "去开始聊天" }),
        ).toBeVisible();
        const emptyHeight = await page
          .locator(".home-empty")
          .evaluate((node) => Math.ceil(node.getBoundingClientRect().height));
        expect(emptyHeight).toBeLessThan(88);
      }
      await page.screenshot({
        path: `test-results/home-encounter-${c.id}-${width}x${height}.png`,
      });
    }
  }
  await page.goto("/#/home/nanally");
  await expect(page.locator(".recent-card")).toHaveCount(2);
  await page
    .locator(".recent-card")
    .filter({ hasText: "你最近正在忙" })
    .click();
  await expect(page).toHaveURL(/#\/memory\/nanally/);
  await page.goto("/#/home/nanally");
  await page
    .locator(".recent-card")
    .filter({ hasText: "最近工作有点多" })
    .click();
  await expect(page).toHaveURL(/turn=home-encounter-turn/);
  for (const [label, route] of [
    ["继续上次对话", "chat"],
    ["查看回忆", "history"],
    ["切换角色", "characters"],
    ["管理记忆", "memory"],
  ]) {
    await page.goto("/#/home/nanally");
    await page
      .locator(".quick-grid")
      .getByRole("button", { name: new RegExp(label) })
      .click();
    await expect(page).toHaveURL(new RegExp(`#/${route}/nanally`));
  }
  await page.goto("/#/home/nanally");
  await page
    .getByRole("button", { name: "看看她记得什么", exact: true })
    .click();
  await expect(page).toHaveURL(/#\/memory\/nanally/);
  await page.goto("/#/home/nanally");
  await page.getByRole("button", { name: "查看全部角色", exact: true }).click();
  await expect(page).toHaveURL(/#\/characters\/nanally/);
  await page.goto("/#/home/nanally");
  await page.locator(".companion-link").filter({ hasText: "伊洛伊" }).click();
  await expect(page).toHaveURL(/#\/chat\/iroi/);
  await page.getByRole("button", { name: "首页", exact: true }).click();
  await expect(page.locator(".home-greeting")).toHaveText(
    characters[1]!.greeting,
  );
  expect(errors).toEqual([]);
});

test("home keeps custom cover precedence and safely falls back without a greeting or scene", async ({
  page,
}) => {
  await fakeApi(page);
  await page.route("**/characters.json", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    const guest = JSON.parse(JSON.stringify(data.characters[0]));
    guest.id = "guest";
    guest.name = "访客";
    guest.versionId = "guest-integration-v1";
    delete guest.sceneDecorations.homeGreeting;
    delete guest.sceneBackground;
    data.characters.push(guest);
    await route.fulfill({ json: data });
  });
  await page.goto("/#/home/guest");
  await expect(page.locator(".home-greeting")).toHaveText("欢迎回来。");
  await expect(page.locator(".home-art img")).toHaveAttribute(
    "src",
    "/media/iroi.image",
  );
  await page.goto("/#/settings/nanally");
  await page.getByRole("button", { name: "外观", exact: true }).click();
  await page
    .locator(".appearance-actions")
    .getByRole("button", { name: "更换封面", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .locator("input[type=file]")
    .setInputFiles("../data/character-assets/iroi.png");
  await expect(dialog.locator(".portrait img").first()).toHaveAttribute(
    "src",
    /^data:image\/png;base64,/,
  );
  await dialog.getByLabel("左右位置").fill("80");
  await dialog.getByRole("button", { name: "保存封面", exact: true }).click();
  await page.getByRole("button", { name: "首页", exact: true }).click();
  await expect(page.locator(".home-art img")).toHaveAttribute(
    "src",
    /^data:image\/png;base64,/,
  );
  await expect(page.locator(".home-art img")).toHaveCSS(
    "object-position",
    "80% 25%",
  );
  await page.reload();
  await expect(page.locator(".home-art img")).toHaveAttribute(
    "src",
    /^data:image\/png;base64,/,
  );
  await page.goto("/#/home/iroi");
  await expect(page.locator(".home-art img")).toHaveAttribute(
    "src",
    "/media/iroi-scene.png",
  );
  await page.goto("/#/settings/nanally");
  await page.getByRole("button", { name: "外观", exact: true }).click();
  await page.getByRole("button", { name: "恢复默认", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "恢复默认", exact: true })
    .click();
  await page.getByRole("button", { name: "首页", exact: true }).click();
  await expect(page.locator(".home-art img")).toHaveAttribute(
    "src",
    "/media/nanally-scene.png",
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
  await expect(page.locator(".topbar .brand")).toContainText("AfterStory");
  await expect(page.locator(".topbar .brand-heart")).toHaveText("♡");
  await expect(page.locator(".topbar .tagline")).toHaveCount(0);
  await expect(page.locator(".composer-caption")).toHaveCount(0);
  await expect(page.getByText("聊天记录保存在本机")).toHaveCount(0);
  for (const label of ["相册", "与娜娜莉的回忆", "一代目的秘密基地"])
    await expect(page.getByRole("button", { name: label })).toBeVisible();
  await expect(page.getByText("哼，回来就好。", { exact: true })).toBeVisible();
  await expect(
    page.getByText("一直在这里，和你💗", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".atmosphere-copy-top")).toContainText(
    "今天又发生什么了？",
  );
  await expect(page.locator(".atmosphere-copy-bottom")).toContainText(
    "有本一代目在",
  );
  await page.getByRole("textbox", { name: "消息" }).fill("今天下雨了");
  await page.getByRole("button", { name: "发送", exact: true }).click();
  await expect(
    page.getByText("收到：今天下雨了", { exact: true }),
  ).toBeVisible();
  const composition = await page.locator(".chat-workspace").evaluate((root) => {
    const scene = root.querySelector(".chat-character-scene")!;
    const portrait = root.querySelector(".scene-portrait")!;
    const interlock = root.querySelector(".scene-interlock")!;
    const sceneImage = portrait.querySelector("img")!;
    const glass = root.querySelector(".chat-glass")!;
    const rootBox = root.getBoundingClientRect();
    const sceneBox = scene.getBoundingClientRect();
    const portraitBox = portrait.getBoundingClientRect();
    const glassBox = glass.getBoundingClientRect();
    const glassStyle = getComputedStyle(glass);
    const glassMaterialStyle = getComputedStyle(glass, "::before");
    const inputShell = root.querySelector(".input-shell")!;
    const menuItems = [...root.querySelectorAll(".scene-space button")];
    const signature = root.querySelector(".scene-signature")!;
    const topNote = root.querySelector(".atmosphere-copy-top")!;
    const bottomNote = root.querySelector(".atmosphere-copy-bottom")!;
    const interlockStyle = getComputedStyle(interlock);
    const sceneImageStyle = getComputedStyle(sceneImage);
    return {
      display: getComputedStyle(root).display,
      sceneCoversFrame:
        Math.abs(sceneBox.left - rootBox.left) <= 1.5 &&
        Math.abs(sceneBox.right - rootBox.right) <= 1.5 &&
        Math.abs(sceneBox.top - rootBox.top) <= 1.5 &&
        Math.abs(sceneBox.bottom - rootBox.bottom) <= 1.5,
      glassFloatsOverScene:
        glassStyle.position === "absolute" &&
        glassBox.left > rootBox.left + rootBox.width * 0.35 &&
        glassBox.right < rootBox.right,
      portraitCrossesIntoGlass:
        portraitBox.right > glassBox.left + glassBox.width * 0.35,
      interlockCreatesBridge:
        interlockStyle.display === "block" &&
        interlockStyle.zIndex === "5" &&
        interlockStyle.maskImage !== "none",
      sceneUsesCharacterBackground:
        sceneImage.getAttribute("src") === "/media/nanally-scene.png" &&
        sceneImageStyle.objectFit === "cover" &&
        sceneImageStyle.objectPosition === "50% 50%",
      glassUsesBackdrop: glassMaterialStyle.backdropFilter !== "none",
      glassUsesLayeredGradient:
        glassMaterialStyle.backgroundImage.includes("radial-gradient") &&
        glassMaterialStyle.backgroundImage.includes("linear-gradient"),
      inputRemainsTranslucent:
        parseFloat(
          getComputedStyle(inputShell).backgroundColor.split(",")[3] || "1",
        ) < 1,
      menuHasDesignedIrregularity:
        menuItems.some((item) => item.classList.contains("icon-start")) &&
        menuItems.some((item) => item.classList.contains("icon-end")) &&
        new Set(
          menuItems.map((item) => getComputedStyle(item, "::after").width),
        ).size > 1,
      signatureLooksHandwritten:
        getComputedStyle(signature).fontFamily.includes("Kaiti") &&
        getComputedStyle(signature).transform !== "none",
      notesUseDifferentAngles:
        getComputedStyle(topNote).fontFamily.includes("Kaiti") &&
        getComputedStyle(topNote).transform !==
          getComputedStyle(bottomNote).transform,
      viewportDoesNotScroll:
        document.documentElement.scrollHeight <= window.innerHeight &&
        document.body.scrollHeight <= window.innerHeight,
    };
  });
  expect(composition).toEqual({
    display: "block",
    sceneCoversFrame: true,
    glassFloatsOverScene: true,
    portraitCrossesIntoGlass: true,
    interlockCreatesBridge: true,
    sceneUsesCharacterBackground: true,
    glassUsesBackdrop: true,
    glassUsesLayeredGradient: true,
    inputRemainsTranslucent: true,
    menuHasDesignedIrregularity: true,
    signatureLooksHandwritten: true,
    notesUseDifferentAngles: true,
    viewportDoesNotScroll: true,
  });
  await page.screenshot({ path: "test-results/chat-desktop.png" });
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
  await expect(
    page.getByText("今天也想做个好孩子，陪你一会儿。", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".atmosphere-copy-top")).toContainText(
    "今天发生的事",
  );
  await expect(
    page.getByRole("button", { name: "伊洛伊的白日梦" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "回忆", exact: true }).click();
  await page.locator(".history-row").click();
  await expect(
    page.locator(".chat-workspace").getByText("收到：今天下雨了", {
      exact: true,
    }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("short desktop empty states and settings overflow remain internally reachable", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await fakeApi(page, false, { memory: true });
  for (const route of ["home", "chat", "history", "memory", "settings"]) {
    await page.goto(`/#/${route}/nanally`);
    await expect(page.locator("#main-content")).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollHeight <= innerHeight,
      ),
    ).toBe(true);
  }
  // A taller future settings category must scroll without moving its navigation.
  const nav = page.locator(".settings-nav");
  const before = await nav.boundingBox();
  const panel = page.locator(".settings-panel");
  await panel.evaluate((element) => {
    const row = element.querySelector(".setting-row")!;
    for (let i = 0; i < 12; i++) element.append(row.cloneNode(true));
    element.scrollTop = element.scrollHeight;
  });
  expect(await panel.evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
  expect(await nav.boundingBox()).toEqual(before);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollHeight <= innerHeight,
    ),
  ).toBe(true);

  await page.goto("/#/memory/nanally");
  await page
    .getByRole("button", { name: "添加第一条记忆", exact: true })
    .click();
  await expect(page.getByLabel("希望她记住什么？")).toBeVisible();
  const filters = page.locator(".collection-filters");
  const fixed = await filters.boundingBox();
  await page.locator(".collection-scroll").evaluate((el) => {
    el.scrollTop = el.scrollHeight;
  });
  await expect(
    page.getByRole("button", { name: "保存", exact: true }),
  ).toBeVisible();
  expect(await filters.boundingBox()).toEqual(fixed);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollHeight <= innerHeight,
    ),
  ).toBe(true);
});

test("scene decorations follow every character and fall back safely", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await fakeApi(page);
  await page.route("**/characters.json", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    const guest = {
      ...data.characters[0],
      id: "guest",
      name: "访客",
      versionId: "guest-integration-v1",
      default: false,
    };
    delete guest.sceneDecorations;
    data.characters.push(guest);
    await route.fulfill({ json: data });
  });

  const cases = [
    {
      id: "nanally",
      accent: "#cf3979",
      background: "/media/nanally-scene.png",
      avatar: "一直在这里，和你💗",
      memory: "与娜娜莉的回忆",
      third: "一代目的秘密基地",
      signature: "哼，回来就好。",
      top: "今天又发生什么了？",
      bottom: "有本一代目在",
      topRotate: "rotate(-5.5deg)",
      bottomRotate: "rotate(4.2deg)",
    },
    {
      id: "iroi",
      accent: "#507c68",
      background: "/media/iroi-scene.png",
      avatar: "今天也想做个好孩子，陪你一会儿。",
      memory: "与伊洛伊的回忆",
      third: "伊洛伊的白日梦",
      signature: "你来了呀……",
      top: "今天发生的事",
      bottom: "如果累了",
      topRotate: "rotate(-3deg)",
      bottomRotate: "rotate(2deg)",
    },
    {
      id: "mint",
      accent: "#167e88",
      background: "/media/mint-scene.png",
      avatar: "闻到啦，你今天也来找我了！",
      memory: "与薄荷的回忆",
      third: "薄荷的小基地",
      signature: "嘿嘿，被我抓到啦。",
      top: "今天有什么新鲜事？",
      bottom: "放心放心",
      topRotate: "rotate(-6deg)",
      bottomRotate: "rotate(4deg)",
    },
  ];
  const noteColors: string[] = [];

  for (const item of cases) {
    await page.goto(`/#/chat/${item.id}`);
    await expect(page.locator(".application")).toHaveCSS(
      "--accent",
      item.accent,
    );
    await expect(page.locator(".scene-portrait img")).toHaveAttribute(
      "src",
      item.background,
    );
    await expect(page.getByText(item.avatar, { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: item.memory })).toBeVisible();
    await expect(page.getByRole("button", { name: item.third })).toBeVisible();
    await expect(page.locator(".scene-signature")).toContainText(
      item.signature,
    );
    const topNote = page.locator(".atmosphere-copy-top");
    const bottomNote = page.locator(".atmosphere-copy-bottom");
    await expect(topNote).toContainText(item.top);
    await expect(bottomNote).toContainText(item.bottom);
    await expect(topNote).toHaveCSS("transform", /matrix/);
    const inlineStyles = await page
      .locator(".chat-workspace")
      .evaluate((root) => {
        const top = root.querySelector<HTMLElement>(".atmosphere-copy-top")!;
        const bottom = root.querySelector<HTMLElement>(
          ".atmosphere-copy-bottom",
        )!;
        return {
          topTransform: top.style.transform,
          bottomTransform: bottom.style.transform,
          topPosition: `${top.style.top}|${top.style.right}`,
          bottomPosition: `${bottom.style.bottom}|${bottom.style.right}`,
          topColor: getComputedStyle(top).color,
          sceneAnimation: getComputedStyle(root.querySelector(".scene-space")!)
            .animationName,
          viewportLocked:
            document.documentElement.scrollHeight <= innerHeight &&
            document.body.scrollHeight <= innerHeight,
        };
      });
    expect(inlineStyles.topTransform).toBe(item.topRotate);
    expect(inlineStyles.bottomTransform).toBe(item.bottomRotate);
    expect(inlineStyles.topPosition).not.toBe("|");
    expect(inlineStyles.bottomPosition).not.toBe("|");
    expect(inlineStyles.sceneAnimation).toContain("decoration-enter");
    expect(inlineStyles.viewportLocked).toBe(true);
    noteColors.push(inlineStyles.topColor);
    await page.screenshot({
      path: `test-results/chat-${item.id}-decorations.png`,
    });
  }

  expect(new Set(noteColors).size).toBe(3);
  await expect(
    page.getByText("一直在这里，和你💗", { exact: true }),
  ).toHaveCount(0);

  await page.goto("/#/chat/guest");
  await expect(page.getByText("一直在这里。", { exact: true })).toBeVisible();
  for (const label of ["相册", "与访客的回忆", "她的小世界"])
    await expect(page.getByRole("button", { name: label })).toBeVisible();
  await expect(page.getByText("欢迎回来。", { exact: true })).toBeVisible();
  await expect(page.locator(".atmosphere-copy")).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("chat visual density keeps simulated dialogue readable without page scrolling", async ({
  page,
}) => {
  const id = "visual-chat";
  const visualTurn: Turn = {
    turn_id: "visual-turn",
    request_id: "visual-request",
    sequence: 1,
    status: "completed",
    error_code: null,
    created_at: timestamp,
    messages: [
      { message_id: "visual-1", role: "assistant", text: "你回来啦。" },
      {
        message_id: "visual-2",
        role: "assistant",
        text: "今天看起来有点累，发生什么了吗？",
      },
      { message_id: "visual-3", role: "user", text: "今天上班有点累。" },
      {
        message_id: "visual-4",
        role: "user",
        text: "最近事情有点多，感觉脑子都转不动了。还好现在终于能慢下来一会儿。",
      },
      {
        message_id: "visual-5",
        role: "assistant",
        text: "那先别想工作的事了。",
      },
      { message_id: "visual-6", role: "assistant", text: "陪我待一会儿吧？" },
      { message_id: "visual-7", role: "user", text: "好。" },
      {
        message_id: "visual-8",
        role: "assistant",
        text: "嗯，那今天什么都不用急。",
      },
      {
        message_id: "visual-9",
        role: "assistant",
        text: "慢一点也没关系，我在这里。",
      },
    ],
  };
  await fakeApi(page, false, {
    sessions: [session(id, "nanally-integration-v1")],
    turns: { [id]: [visualTurn] },
  });
  await page.goto(`/#/chat/nanally?conversation=${id}`);
  await expect(page.locator(".message")).toHaveCount(9);
  const visualCheck = await page.locator(".chat-workspace").evaluate((root) => {
    const messages = root.querySelector(".messages")!;
    const assistant = root.querySelector(".message.assistant .bubble")!;
    const user = root.querySelector(".message.user .bubble")!;
    const repeatedAuthor = root.querySelector(
      ".message.assistant + .message.assistant .message-author",
    )!;
    const userBox = user.getBoundingClientRect();
    const messagesBox = messages.getBoundingClientRect();
    return {
      viewportLocked:
        document.documentElement.scrollHeight <= window.innerHeight &&
        document.body.scrollHeight <= window.innerHeight,
      userWidthIsRestrained: userBox.width <= messagesBox.width * 0.7 + 1,
      assistantUsesLightTreatment:
        getComputedStyle(assistant).borderLeftWidth === "2px",
      repeatedAssistantMetadataIsQuiet:
        getComputedStyle(repeatedAuthor).display === "none",
    };
  });
  expect(visualCheck).toEqual({
    viewportLocked: true,
    userWidthIsRestrained: true,
    assistantUsesLightTreatment: true,
    repeatedAssistantMetadataIsQuiet: true,
  });
  const input = page.getByRole("textbox", { name: "消息" });
  await input.focus();
  await expect(input).toBeFocused();
  await page.screenshot({ path: "test-results/chat-visual-density.png" });
});

test("chat empty state remains secondary to the character scene", async ({
  page,
}) => {
  await fakeApi(page);
  await page.goto("/#/chat/nanally");
  const welcome = page.locator(".chat-workspace .welcome");
  await expect(welcome).toBeVisible();
  await expect(page.getByRole("textbox", { name: "消息" })).toBeEnabled();
  const emptyCheck = await welcome.evaluate((welcome) => {
    const root = welcome.closest(".chat-workspace")!;
    const messages = welcome.closest(".messages")!;
    return {
      noMessages: root.querySelectorAll(".message").length === 0,
      viewportLocked:
        document.documentElement.scrollHeight <= window.innerHeight &&
        document.body.scrollHeight <= window.innerHeight,
      welcomeIsSubdued: Number(getComputedStyle(welcome).opacity) < 0.8,
      messageAreaOwnsScrolling: getComputedStyle(messages).overflowY === "auto",
    };
  });
  expect(emptyCheck).toEqual({
    noMessages: true,
    viewportLocked: true,
    welcomeIsSubdued: true,
    messageAreaOwnsScrolling: true,
  });
  await page.screenshot({ path: "test-results/chat-empty-state.png" });
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
  await page.getByLabel("更多操作").click();
  await page.getByRole("button", { name: "更正" }).click();
  await page.getByLabel("更正记忆内容").fill("我喜欢在小雨的夜晚散步");
  await page.getByRole("button", { name: "保存更正" }).click();
  await expect(
    page.getByText("我喜欢在小雨的夜晚散步", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "查看来源" }).click();
  await expect(page.locator(".source-turn")).toContainText("我喜欢在雨天散步");
  await page.goto("/#/memory/nanally");
  await page.getByLabel("更多操作").click();
  await page.getByRole("button", { name: "删除" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "确认删除" })
    .click();
  await expect(
    page.getByRole("heading", { name: "她还没有留下特别的记忆" }),
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

test("characters make the current world prominent while keeping the other two visible", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await fakeApi(page);

  for (const [width, height] of [
    [1920, 1080],
    [1600, 900],
    [1440, 900],
    [1366, 768],
  ]) {
    await page.setViewportSize({ width, height });
    await page.goto("/#/characters/nanally");
    await expect(page.locator(".character-panel")).toHaveCount(3);
    await expect(page.locator(".character-panel.featured")).toContainText(
      "当前角色",
    );
    await expect(page.locator(".character-panel.featured")).toContainText(
      "哼，回来就好。",
    );
    await expect(page.locator(".other-characters")).toContainText("伊洛伊");
    await expect(page.locator(".other-characters")).toContainText("薄荷");
    const composition = await page
      .locator(".selection-page")
      .evaluate((root) => {
        const featured = root
          .querySelector(".character-panel.featured")!
          .getBoundingClientRect();
        const secondary = root
          .querySelector(".other-characters .character-panel")!
          .getBoundingClientRect();
        const others = root.querySelector(".other-characters")!;
        return {
          viewportLocked:
            document.documentElement.scrollHeight <= innerHeight &&
            document.documentElement.scrollWidth <= innerWidth,
          featuredDominates: featured.width > secondary.width * 1.35,
          otherRolesFitWithoutScrolling:
            others.scrollHeight <= others.clientHeight + 1,
        };
      });
    expect(composition).toEqual({
      viewportLocked: true,
      featuredDominates: true,
      otherRolesFitWithoutScrolling: true,
    });
    if (width === 1366)
      await page.screenshot({
        path: `test-results/characters-stage-${width}x${height}.png`,
      });
  }

  for (const [id, name, signature, accent] of [
    ["iroi", "伊洛伊", "你来了呀……", "#507c68"],
    ["mint", "薄荷", "嘿嘿，被我抓到啦。", "#167e88"],
  ]) {
    await page.goto(`/#/characters/${id}`);
    await expect(page.locator(".application")).toHaveCSS("--accent", accent);
    await expect(page.locator(".character-panel.featured")).toContainText(name);
    await expect(page.locator(".character-panel.featured")).toContainText(
      signature,
    );
  }

  await page.goto("/#/characters/nanally");
  await page.getByRole("button", { name: "继续和娜娜莉" }).click();
  await expect(page).toHaveURL(/#\/chat\/nanally/);
  await page.getByRole("button", { name: "角色", exact: true }).click();
  await page.getByRole("button", { name: "去见伊洛伊" }).click();
  await expect(page).toHaveURL(/#\/chat\/iroi/);
  expect(errors).toEqual([]);
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
  await page.setViewportSize({ width: 1440, height: 620 });
  const scrollBoundaries = await page
    .locator(".messages")
    .evaluate((messages) => ({
      viewportLocked:
        document.documentElement.scrollHeight <= window.innerHeight &&
        document.body.scrollHeight <= window.innerHeight,
      messagesCanScroll: messages.scrollHeight > messages.clientHeight,
    }));
  expect(scrollBoundaries).toEqual({
    viewportLocked: true,
    messagesCanScroll: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
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
  await page.getByRole("button", { name: "加载更多记忆" }).click();
  await expect(page.locator(".memory-list article")).toHaveCount(101);
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
  await page
    .locator(".character-chips button")
    .filter({ hasText: "伊洛伊" })
    .click();
  await expect(page.locator(".history-row")).toHaveCount(1);
  await expect(page.locator(".history-row")).toContainText("伊洛伊的雨天");
  await expect(page.locator(".history-row")).toContainText("未记录时间");
  await expect(page.locator(".history-row")).not.toContainText(
    "integration-v1",
  );
});

test("memories page presents compact empty and populated journal states", async ({
  page,
}) => {
  const historySamples: Session[] = [
    {
      ...session("nanally-visual", "nanally-integration-v1"),
      name: "娜娜莉",
      turns: 4,
      last_activity_at: "2026-09-15T23:42:00Z",
      preview:
        "“最近工作事情有点多，感觉脑子都转不动了。”\n她说：“那先别想工作的事了，陪我待一会儿吧。”",
    },
    {
      ...session("iroi-visual", "iroi-integration-v1"),
      name: "伊洛伊",
      turns: 3,
      last_activity_at: "2026-09-14T12:30:00Z",
      preview: "“最近一直在推进自己的项目。”\n她说：“慢慢来也没关系呀。”",
    },
    {
      ...session("mint-visual", "mint-integration-v1"),
      name: "薄荷",
      turns: 3,
      last_activity_at: "2026-09-13T12:30:00Z",
      preview: "“今天发生了一件挺有意思的小事。”\n她说：“快说快说，我要听！”",
    },
    {
      ...session("nanally-rest", "nanally-integration-v1"),
      name: "娜娜莉",
      turns: 2,
      last_activity_at: "2026-09-12T12:30:00Z",
      preview: "“今天什么都不想做。”\n她说：“那今天就什么都不做。”",
    },
  ];
  const id = "nanally-integration-v1";
  await fakeApi(page, false, {
    memory: true,
    sessions: historySamples,
    memories: [
      memory(
        "work-memory",
        `instance-${id}`,
        "她记得你最近工作比较累\n\n“最近事情很多，下班后有时候只想安静待着。”",
        "2026-09-13T12:30:00Z",
      ),
      memory(
        "project-memory",
        `instance-${id}`,
        "她记得你正在认真做自己的项目\n\n“你想把喜欢的角色真正做成可以长期陪伴的产品。”",
        "2026-09-11T12:30:00Z",
      ),
      memory(
        "share-memory",
        `instance-${id}`,
        "她记得你喜欢分享每天的小事\n\n“哪怕只是今天吃了什么，也值得说一说。”",
        "2026-09-09T12:30:00Z",
      ),
      memory(
        "quiet-memory",
        `instance-${id}`,
        "她记得你也需要什么都不做的下午\n\n“有时候安静待着，也是一件重要的事。”",
        "2026-09-08T12:30:00Z",
      ),
    ],
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/#/history/nanally");
  await expect(page.locator(".history-row")).toHaveCount(4);
  await expect(page.locator(".history-scroll")).toContainText("陪我待一会儿吧");
  await expect(page.locator(".history-scroll")).toContainText("快说快说，我要听！");
  await page.screenshot({ path: "test-results/memories-history-populated.png" });
  await page.getByLabel("搜索回忆").fill("推进自己的项目");
  await expect(page.locator(".history-row")).toHaveCount(1);
  await page.screenshot({ path: "test-results/memories-history-filtered.png" });
  await page.getByLabel("搜索回忆").fill("");

  await page.getByRole("tab", { name: /她记得的事/ }).click();
  await expect(page.locator(".memory-list article")).toHaveCount(4);
  await expect(page.locator(".memory-list")).toContainText("认真做自己的项目");
  await expect(page.getByLabel("更多操作").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "更正" })).toHaveCount(0);
  await page.screenshot({ path: "test-results/memories-facts-populated.png" });

  await fakeApi(page, false, { memory: true });
  await page.goto("/#/history/nanally");
  await expect(page.locator(".history-scroll .empty")).toContainText(
    "第一段回忆，还在等你们一起写下。",
  );
  await page.screenshot({ path: "test-results/memories-history-empty.png" });
  await page.getByRole("tab", { name: /她记得的事/ }).click();
  await expect(page.locator(".memory-empty")).toContainText(
    "她还没有留下特别的记忆",
  );
  await page.screenshot({ path: "test-results/memories-facts-empty.png" });
});

test("every primary page stays usable across supported desktop widths", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await fakeApi(page, false, { memory: true });

  for (const width of [900, 1440, 1600, 1920]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const route of [
      "home",
      "characters",
      "chat",
      "history",
      "memory",
      "settings",
    ]) {
      await page.goto(`/#/${route}/nanally`);
      await expect(page.locator("#main-content")).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
        `${route} at ${width}px should not create horizontal overflow`,
      ).toBe(true);
      if (route === "chat") {
        expect(
          await page.evaluate(
            () => document.documentElement.scrollHeight <= window.innerHeight,
          ),
          `chat at ${width}px should not create page-level vertical overflow`,
        ).toBe(true);
      }
    }
  }
  expect(errors).toEqual([]);
});

test("settings keeps every preference category in one quiet workspace", async ({
  page,
}) => {
  await fakeApi(page, false, { memory: true });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/#/settings/nanally");
  await expect(
    page.getByRole("heading", { name: "按你的习惯来" }),
  ).toBeVisible();
  await expect(page.locator(".settings-companion")).toContainText("娜娜莉");

  for (const [label, panel] of [
    ["通用", "阅读与交流"],
    ["外观", "角色主题与封面"],
    ["声音", "声音"],
    ["数据管理", "数据管理"],
  ]) {
    await page
      .getByRole("navigation", { name: "设置类别" })
      .getByRole("button", { name: label, exact: true })
      .click();
    await expect(page.locator(".settings-panel")).toContainText(panel);
    await expect(page.locator(".settings-panel")).toHaveCSS(
      "overflow-y",
      "auto",
    );
    await page.screenshot({
      path: `test-results/settings-${label}.png`,
    });
  }
  expect(
    await page.evaluate(
      () => document.documentElement.scrollHeight <= window.innerHeight,
    ),
  ).toBe(true);
});

test("desktop viewport sizes keep core pages and controls inside the screen", async ({
  page,
}) => {
  test.setTimeout(60000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const id = "nanally-integration-v1";
  await fakeApi(page, false, {
    memory: true,
    sessions: [
      session(id),
      ...Array.from({ length: 24 }, (_, i) => ({
        ...session(`desktop-history-${i}`, id),
        turns: 3,
        preview: `已保存的回忆 ${i}`,
      })),
    ],
    turns: {
      [id]: Array.from({ length: 40 }, (_, i) =>
        turn(
          `desktop-turn-${i}`,
          i + 1,
          "今天想聊聊最近发生的事情。".repeat(5),
        ),
      ),
    },
    memories: Array.from({ length: 30 }, (_, i) =>
      memory(
        `desktop-memory-${i}`,
        `instance-${id}`,
        `主动保存的个人记忆 ${i}：` +
          "这是一条需要完整阅读的记忆内容。".repeat(10),
      ),
    ),
  });
  for (const [width, height] of [
    [1920, 1080],
    [1600, 900],
    [1440, 900],
    [1366, 768],
  ]) {
    await page.setViewportSize({ width, height });
    for (const route of [
      "home",
      "characters",
      "chat",
      "history",
      "memory",
      "settings",
    ]) {
      await page.goto(`/#/${route}/nanally`);
      await expect(page.locator("#main-content")).toBeVisible();
      if (route === "home")
        await expect(page.locator(".recent-card")).toHaveCount(3);
      if (route === "chat")
        await expect(page.getByRole("textbox", { name: "消息" })).toBeEnabled();
      if (route === "history")
        await expect(page.locator(".history-row").first()).toBeVisible();
      if (route === "memory")
        await expect(page.locator(".memory-list article")).toHaveCount(30);
      const sizes = await page.evaluate(() => {
        const main = document.querySelector<HTMLElement>("#main-content")!;
        const header = document.querySelector<HTMLElement>(".topbar")!;
        const rect = main.getBoundingClientRect();
        return {
          body: document.body.scrollHeight,
          document: document.documentElement.scrollHeight,
          main: Math.round(rect.height),
          bottom: Math.round(rect.bottom),
          header: Math.round(header.getBoundingClientRect().height),
          headerTop: Math.round(header.getBoundingClientRect().top),
          horizontal: document.documentElement.scrollWidth,
          pageOverflow: getComputedStyle(main).overflowY,
        };
      });
      console.log(`${width}x${height} ${route}: ${JSON.stringify(sizes)}`);
      expect(sizes.body, `${route} body`).toBeLessThanOrEqual(height);
      expect(sizes.document, `${route} document`).toBeLessThanOrEqual(height);
      expect(sizes.bottom, `${route} main bottom`).toBeLessThanOrEqual(height);
      expect(sizes.horizontal, `${route} horizontal`).toBeLessThanOrEqual(
        width,
      );
      expect(sizes.header).toBe(72);
      expect(sizes.headerTop).toBe(0);
      expect(sizes.pageOverflow).toBe("hidden");

      const controls =
        route === "home"
          ? ".hero-action, .welcome-footnote, .quick-grid button, .companion-link, .recent-card"
          : route === "characters"
            ? ".character-card .visit-action"
            : route === "chat"
              ? ".chat-header, .composer-field"
              : route === "settings"
                ? ".settings-nav button"
                : ".memory-tabs, .history-controls, .collection-filters";
      expect(
        await page.locator(controls).evaluateAll((elements) =>
          elements.every((element) => {
            const rect = element.getBoundingClientRect();
            const card = element
              .closest(
                ".character-card, .home-welcome, .home-middle, .other-companions",
              )
              ?.getBoundingClientRect();
            return (
              rect.top >= 0 &&
              rect.bottom <= innerHeight + 1 &&
              rect.left >= 0 &&
              rect.right <= innerWidth + 1 &&
              (!card ||
                (rect.top >= card.top && rect.bottom <= card.bottom + 1))
            );
          }),
        ),
        `${route} controls must not be clipped`,
      ).toBe(true);

      if (["chat", "history", "memory"].includes(route)) {
        const scroll = page.locator(
          route === "chat"
            ? ".messages"
            : route === "history"
              ? ".history-scroll"
              : ".collection-scroll",
        );
        const fixed = page.locator(
          route === "chat"
            ? ".chat-header"
            : route === "history"
              ? ".history-controls"
              : ".collection-filters",
        );
        const before = await fixed.boundingBox();
        expect(
          await scroll.evaluate((el) => getComputedStyle(el).overflowY),
        ).toBe("auto");
        const canScroll = await scroll.evaluate(
          (el) => el.scrollHeight > el.clientHeight,
        );
        if (canScroll) {
          await scroll.evaluate((el) => {
            el.scrollTop = el.scrollHeight;
          });
          expect(await scroll.evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
        }
        expect(await fixed.boundingBox()).toEqual(before);
      }
      if (route === "settings") {
        for (const label of ["通用", "外观", "声音", "数据管理"]) {
          await page
            .getByRole("navigation", { name: "设置类别" })
            .getByRole("button", { name: label, exact: true })
            .click();
          await expect(page.locator(".settings-panel")).toHaveCSS(
            "overflow-y",
            "auto",
          );
          const box = await page.locator(".settings-panel").boundingBox();
          expect(box!.y + box!.height).toBeLessThanOrEqual(height);
          if (
            (width === 1440 || width === 1366) &&
            ["通用", "外观"].includes(label)
          ) {
            await page.screenshot({
              path: `test-results/desktop-${width}x${height}-settings-${label === "通用" ? "general" : "appearance"}.png`,
            });
          }
        }
      }
      await page.screenshot({
        path: `test-results/desktop-${width}x${height}-${route}.png`,
      });
    }
  }
  expect(errors).toEqual([]);
});
