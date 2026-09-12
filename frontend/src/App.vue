<script setup lang="ts">
import {
  computed,
  nextTick,
  onMounted,
  onUnmounted,
  reactive,
  ref,
  watch,
} from "vue";
import {
  ArrowLeft,
  ArrowUp,
  BookOpen,
  Check,
  ChevronDown,
  History as HistoryIcon,
  ImagePlus,
  LoaderCircle,
  MessageCircle,
  RotateCcw,
  Settings,
  Sparkles,
  Volume2,
} from "lucide-vue-next";
import { api, errorText } from "./api";
import { coverStorage } from "./storage";
import type { Character, Cover, History, Session, Turn } from "./types";
import Portrait from "./Portrait.vue";
import CoverEditor from "./CoverEditor.vue";

const characters = ref<Character[]>([]);
const selected = ref("nanally");
const page = ref("chat");
const section = ref("general");
const hovered = ref("nanally");
const user = ref("");
const connected = ref(false);
const busy = ref(false);
const notice = ref("");
const fatal = ref("");
const editing = ref(false);
const resetConfirm = ref(false);
const covers = reactive<Record<string, Cover>>({});
const sessions = ref<Session[]>([]);
const historyLoading = ref(false);
const historyError = ref("");
const scrollArea = ref<HTMLElement>();
const preferences = reactive({
  font: "standard",
  send: "enter",
  motion: true,
  voice: "manual",
});
type Chat = {
  id: string;
  turns: Turn[];
  total: number;
  offset: number;
  draft: string;
  loading: boolean;
  sending: boolean;
  error: string;
  pending?: { request_id: string; text: string };
};
const chats = reactive<Record<string, Chat>>({});
const character = computed(
  () =>
    characters.value.find((c) => c.id === selected.value) ||
    characters.value[0],
);
const chat = computed(() => chats[selected.value]);
const theme = computed(() =>
  Object.fromEntries(
    Object.entries(character.value?.theme || {}).map(([key, value]) => [
      `--${key}`,
      value,
    ]),
  ),
);
const key = (suffix: string) => `afterstory:${user.value}:${suffix}`;
const cover = (c: Character) =>
  covers[c.id] || { source: c.cover, crop: c.crop };
function store(name: string, value: unknown) {
  try {
    localStorage.setItem(key(name), JSON.stringify(value));
  } catch {
    notice.value = "浏览器空间不足，本次更改可能无法在刷新后保留。";
  }
}
function read<T>(name: string, fallback: T): T {
  try {
    return JSON.parse(localStorage.getItem(key(name)) || "null") ?? fallback;
  } catch {
    return fallback;
  }
}
function saveChat(id: string) {
  const state = chats[id];
  if (state)
    store(`draft:${id}`, {
      id: state.id,
      draft: state.draft,
      pending: state.pending,
    });
}
function route(next: string) {
  location.hash = `/${next}/${selected.value}`;
}
function routeChanged() {
  const [, next, id] = location.hash.split("/");
  page.value = [
    "chat",
    "characters",
    "profile",
    "history",
    "settings",
    "memory",
  ].includes(next || "")
    ? next!
    : "chat";
  if (characters.value.some((c) => c.id === id)) selected.value = id!;
  if (connected.value && page.value === "chat") void openChat(selected.value);
  if (connected.value && page.value === "history") void loadSessions();
}
function choose(c: Character) {
  selected.value = c.id;
  store("selected", c.id);
  route("chat");
}
async function connect() {
  busy.value = true;
  fatal.value = "";
  try {
    const result = await api<{ user_id: string }>("/health");
    user.value = result.user_id;
    Object.assign(preferences, read("preferences", preferences));
    if (!location.hash) selected.value = read("selected", selected.value);
    for (const c of characters.value) {
      const saved = read<{
        id?: string;
        draft: string;
        pending?: Chat["pending"];
      }>(`draft:${c.id}`, { draft: "" });
      chats[c.id] = {
        id: saved.id || "",
        turns: [],
        total: 0,
        offset: 0,
        draft: saved.draft,
        pending: saved.pending,
        loading: false,
        sending: false,
        error: "",
      };
      try {
        const savedCover = await coverStorage(key(`cover:${c.id}`));
        if (savedCover) covers[c.id] = savedCover;
      } catch {
        notice.value = "当前浏览器无法读取自定义封面。";
      }
    }
    connected.value = true;
    routeChanged();
  } catch (error) {
    connected.value = false;
    fatal.value = errorText(error);
  } finally {
    busy.value = false;
  }
}
async function refresh(id: string, older = false) {
  const state = chats[id]!;
  if (!state.id) return;
  let offset = older ? Math.max(0, state.offset - 30) : 0;
  if (!older) {
    const count = await api<History>(
      `/conversations/${state.id}/messages?limit=1`,
    );
    offset = Math.max(0, count.total - 30);
  }
  const result = await api<History>(
    `/conversations/${state.id}/messages?offset=${offset}&limit=30`,
  );
  state.turns = older
    ? [
        ...result.turns.filter(
          (t) => !state.turns.some((old) => old.turn_id === t.turn_id),
        ),
        ...state.turns,
      ]
    : result.turns;
  state.total = result.total;
  state.offset = offset;
  if (
    state.pending &&
    state.turns.some(
      (t) =>
        t.request_id === state.pending?.request_id && t.status === "completed",
    )
  ) {
    state.pending = undefined;
    saveChat(id);
  }
  if (state.pending && !state.sending)
    state.error = "有一条尚未完成的消息，点击重试继续发送。";
  if (!older) {
    await nextTick();
    if (id === selected.value)
      scrollArea.value?.scrollTo({ top: scrollArea.value.scrollHeight });
  }
}
async function openChat(id: string, conversationId?: string) {
  const state = chats[id];
  const c = characters.value.find((item) => item.id === id);
  if (!state || !c || state.loading || state.sending) return;
  state.loading = true;
  state.error = "";
  try {
    if (conversationId) state.id = conversationId;
    else if (!state.id)
      state.id = (
        await api<{ conversation_id: string }>("/sessions/open", {
          version_id: c.versionId,
        })
      ).conversation_id;
    await refresh(id);
  } catch (error) {
    state.error = errorText(error);
  } finally {
    state.loading = false;
  }
}
async function send(retry?: { request_id: string; text: string }) {
  const id = selected.value;
  const state = chats[id];
  if (
    !state ||
    state.sending ||
    state.loading ||
    !state.id ||
    (!retry && (!state.draft.trim() || state.pending))
  )
    return;
  const pending = retry || {
    request_id: crypto.randomUUID(),
    text: state.draft.trim(),
  };
  state.pending = pending;
  if (!retry) state.draft = "";
  saveChat(id);
  state.sending = true;
  state.error = "";
  try {
    await api(`/conversations/${state.id}/messages`, pending);
    state.pending = undefined;
    saveChat(id);
    await refresh(id);
  } catch (error) {
    state.error = errorText(error);
    try {
      await refresh(id);
    } catch {
      /* Keep the durable outbox when offline. */
    }
  } finally {
    state.sending = false;
  }
}
function inputKey(event: KeyboardEvent) {
  if (event.isComposing || event.keyCode === 229) return;
  if (
    event.key === "Enter" &&
    !event.shiftKey &&
    (preferences.send === "enter"
      ? !event.ctrlKey
      : event.ctrlKey || event.metaKey)
  ) {
    event.preventDefault();
    void send();
  }
}
function recoverDraft() {
  const state = chat.value;
  if (!state?.pending || state.sending) return;
  state.draft = [state.pending.text, state.draft].filter(Boolean).join("\n");
  state.pending = undefined;
  state.error = "";
  saveChat(selected.value);
}
async function loadOlder() {
  const state = chat.value;
  if (!state || state.loading) return;
  state.loading = true;
  try {
    await refresh(selected.value, true);
  } catch (error) {
    state.error = errorText(error);
  } finally {
    state.loading = false;
  }
}
async function loadSessions() {
  historyLoading.value = true;
  historyError.value = "";
  try {
    sessions.value = await api<Session[]>("/conversations");
  } catch (error) {
    historyError.value = errorText(error);
  } finally {
    historyLoading.value = false;
  }
}
async function resume(item: Session) {
  const c = characters.value.find((c) => c.versionId === item.version_id);
  if (!c) return;
  if (chats[c.id]?.pending && chats[c.id]?.id !== item.conversation_id) {
    notice.value = "请先回到当前聊天，处理尚未完成的消息。";
    return;
  }
  selected.value = c.id;
  await openChat(c.id, item.conversation_id);
  route("chat");
}
async function saveCover(value: Cover) {
  const id = selected.value;
  try {
    await coverStorage(key(`cover:${id}`), JSON.parse(JSON.stringify(value)));
    covers[id] = value;
    editing.value = false;
    notice.value = "封面已保存。";
  } catch {
    notice.value = "封面保存失败，调整仍保留，请重试。";
  }
}
async function resetCover() {
  const id = selected.value;
  try {
    await coverStorage(key(`cover:${id}`), null);
    delete covers[id];
    resetConfirm.value = false;
    notice.value = "已恢复默认封面。";
  } catch {
    notice.value = "恢复失败，原封面已保留。";
  }
}
watch(preferences, () => {
  if (user.value) store("preferences", preferences);
});
let previousFocus: HTMLElement | null = null;
watch(
  () => editing.value || resetConfirm.value,
  async (open) => {
    if (open) previousFocus = document.activeElement as HTMLElement;
    await nextTick();
    document
      .querySelectorAll<HTMLElement>(".workspace, .topbar, .selection-page")
      .forEach((element) => {
        element.inert = open;
      });
    if (open) document.querySelector<HTMLElement>(".modal button")?.focus();
    else previousFocus?.focus();
  },
);
function modalKeys(event: KeyboardEvent) {
  if (!editing.value && !resetConfirm.value) return;
  if (event.key === "Escape") {
    editing.value = false;
    resetConfirm.value = false;
    return;
  }
  if (event.key !== "Tab") return;
  const items = [
    ...document.querySelectorAll<HTMLElement>(
      ".modal button:not(:disabled), .modal input:not([type=file]), .modal select",
    ),
  ];
  const first = items[0],
    last = items.at(-1);
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last?.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first?.focus();
  }
}
onMounted(async () => {
  window.addEventListener("hashchange", routeChanged);
  window.addEventListener("keydown", modalKeys);
  try {
    const response = await fetch("/characters.json");
    if (!response.ok) throw new Error("角色配置读取失败");
    characters.value = (await response.json()).characters;
    selected.value =
      characters.value.find((c) => c.default)?.id || characters.value[0]!.id;
    routeChanged();
    await connect();
  } catch {
    fatal.value = "无法读取角色配置，请刷新页面重试。";
  }
});
onUnmounted(() => {
  window.removeEventListener("hashchange", routeChanged);
  window.removeEventListener("keydown", modalKeys);
});
</script>

<template>
  <div
    class="application"
    :style="theme"
    :class="[
      { 'reduce-motion': !preferences.motion },
      `font-${preferences.font}`,
    ]"
  >
    <header class="topbar">
      <a class="brand" href="#/chat" @click.prevent="route('chat')"
        >AfterStory<span></span
      ></a>
      <div class="topbar-line"></div>
      <span class="tagline">故事之外，与你相见</span>
      <nav>
        <button
          :class="{ active: page === 'characters' }"
          @click="
            hovered = selected;
            route('characters');
          "
        >
          角色</button
        ><button
          :class="{ active: page === 'history' }"
          @click="route('history')"
        >
          <HistoryIcon :size="16" />历史</button
        ><button
          :class="{ active: page === 'settings' }"
          @click="route('settings')"
        >
          <Settings :size="16" />设置
        </button>
      </nav>
    </header>
    <div v-if="fatal" class="connection-banner" role="alert">
      {{ fatal
      }}<button :disabled="busy" @click="connect">
        {{ busy ? "连接中…" : "重新连接" }}
      </button>
    </div>
    <div v-if="notice" class="toast" role="status">
      {{ notice }}<button aria-label="关闭提示" @click="notice = ''">×</button>
    </div>
    <template v-if="character">
      <main v-if="page === 'characters'" class="selection-page">
        <div class="page-heading">
          <div>
            <small>ACROSS WORLDS</small>
            <h1>今天，想和谁说说话？</h1>
          </div>
          <p>不同的世界，同一份期待。</p>
        </div>
        <div class="character-accordion" @mouseleave="hovered = selected">
          <button
            v-for="c in characters"
            :key="c.id"
            class="character-panel"
            :class="{ expanded: hovered === c.id }"
            @mouseenter="hovered = c.id"
            @focus="hovered = c.id"
            @click="choose(c)"
          >
            <Portrait
              :source="cover(c).source"
              :crop="cover(c).crop.selection"
              :name="c.name"
            />
            <div class="character-caption">
              <small>{{ c.romanized }}</small>
              <h2>{{ c.name }}</h2>
              <span
                >{{ c.world }}
                <span v-if="c.id === selected">· 当前角色</span></span
              >
            </div>
          </button>
        </div>
        <p class="selection-note">
          悬停看看她 · 点击继续聊天
          <span>角色形象为参考素材，可在设置中替换</span>
        </p>
      </main>
      <main
        v-else
        class="workspace"
        :class="{ 'secondary-workspace': page !== 'chat' }"
      >
        <aside class="character-side">
          <Portrait
            :source="cover(character).source"
            :crop="cover(character).crop.chat"
            :name="character.name"
          /><button
            class="character-switch"
            @click="
              hovered = selected;
              route('characters');
            "
          >
            {{ character.name }}<ChevronDown :size="15" />
          </button>
          <div class="portrait-caption">
            <small>{{ character.world }} / {{ character.romanized }}</small>
            <h1>{{ character.name }}</h1>
            <div>
              <button @click="route('profile')">
                角色资料 <BookOpen :size="15" /></button
              ><button
                aria-label="更换封面"
                :disabled="!connected"
                @click="editing = true"
              >
                <ImagePlus :size="18" />
              </button>
            </div>
          </div>
        </aside>
        <section v-if="page === 'chat'" class="chat-area">
          <header class="chat-heading">
            <div>
              <h2>{{ character.name }}</h2>
              <span
                ><i :class="{ online: connected }"></i
                >{{ connected ? "文字交流已连接" : "等待连接" }}</span
              >
            </div>
            <span class="data-badge">{{ character.dataStatus }}</span>
          </header>
          <div
            ref="scrollArea"
            class="messages"
            aria-live="polite"
            :aria-busy="chat?.loading"
          >
            <button
              v-if="chat?.offset"
              class="load-older"
              :disabled="chat.loading"
              @click="loadOlder"
            >
              查看更早的对话
            </button>
            <div v-if="chat?.loading && !chat.turns.length" class="empty">
              <LoaderCircle class="spin" :size="24" />
              <p>正在找回你们的对话…</p>
            </div>
            <div
              v-else-if="!chat?.turns.length && !chat?.pending"
              class="empty welcome"
            >
              <span class="welcome-mark">✳</span
              ><small>ANOTHER DAY, ANOTHER STORY</small>
              <h2>故事之外，<br />还有话想对你说。</h2>
              <p>从今天的一件小事开始吧。</p>
              <span class="integration-note"
                >当前使用联调角色资料，正式性格与剧情将逐步补全。</span
              >
            </div>
            <div v-for="turn in chat?.turns" :key="turn.turn_id" class="turn">
              <div
                v-for="message in turn.messages"
                :key="message.message_id"
                class="message"
                :class="message.role"
              >
                <span class="message-author">{{
                  message.role === "user" ? "你" : character.name
                }}</span>
                <div class="bubble">{{ message.text }}</div>
              </div>
              <div v-if="turn.status !== 'completed'" class="turn-status">
                {{
                  turn.status === "processing"
                    ? "回复处理中，可刷新确认结果"
                    : "这次回复未完成"
                }}<button
                  v-if="
                    turn.status === 'failed' && turn.sequence === chat?.total
                  "
                  :disabled="chat?.sending"
                  @click="
                    send({
                      request_id: turn.request_id,
                      text: turn.messages.find((m) => m.role === 'user')!.text,
                    })
                  "
                >
                  重试</button
                ><button
                  v-else-if="turn.status === 'processing'"
                  @click="openChat(selected)"
                >
                  刷新
                </button>
              </div>
            </div>
            <div
              v-if="
                chat?.pending &&
                !chat.turns.some(
                  (t) => t.request_id === chat.pending?.request_id,
                )
              "
              class="message user"
            >
              <span class="message-author">你</span>
              <div class="bubble">{{ chat.pending.text }}</div>
            </div>
            <div v-if="chat?.sending" class="reply-wait">
              <span></span><span></span><span></span><small>正在等待回复</small>
            </div>
          </div>
          <form class="composer" @submit.prevent="send()">
            <div v-if="chat?.error" class="chat-error" role="alert">
              {{ chat.error
              }}<button
                type="button"
                :disabled="chat.sending"
                @click="chat.pending ? send(chat.pending) : openChat(selected)"
              >
                重试
              </button>
              <button
                v-if="chat.pending && !chat.sending"
                type="button"
                @click="recoverDraft"
              >
                取回输入框
              </button>
            </div>
            <div class="input-shell">
              <textarea
                v-if="chat"
                v-model="chat.draft"
                aria-label="消息"
                placeholder="想说什么，都可以慢慢说…"
                maxlength="8000"
                rows="2"
                :disabled="!connected"
                @input="saveChat(selected)"
                @keydown="inputKey"
              ></textarea
              ><textarea
                v-else
                aria-label="消息"
                placeholder="连接后，就可以开始聊天…"
                disabled
              ></textarea
              ><button
                class="send-button"
                :aria-label="character.sendControl.label"
                :disabled="
                  !connected ||
                  !chat?.id ||
                  chat.sending ||
                  chat.loading ||
                  !chat.draft.trim() ||
                  !!chat.pending
                "
              >
                <LoaderCircle
                  v-if="chat?.sending"
                  class="spin"
                  :size="20"
                /><img
                  v-else-if="character.sendControl.image"
                  :src="character.sendControl.image"
                  alt=""
                /><ArrowUp v-else :size="21" />
              </button>
            </div>
            <div class="composer-caption">
              <span>{{
                preferences.send === "enter"
                  ? "Enter 发送 · Shift + Enter 换行"
                  : "Ctrl / ⌘ + Enter 发送"
              }}</span
              ><span>聊天记录保存在本机</span>
            </div>
          </form>
        </section>
        <section v-else class="content-area">
          <button class="back-link" @click="route('chat')">
            <ArrowLeft :size="16" />返回聊天
          </button>
          <template v-if="page === 'profile'"
            ><small class="eyebrow"
              >CHARACTER / {{ character.romanized }}</small
            >
            <h1>{{ character.name }}</h1>
            <p class="muted">
              {{ character.world }} · {{ character.dataStatus }}
            </p>
            <section class="prose">
              <h2>关于她</h2>
              <p>{{ character.description }}</p>
              <p class="muted">
                当前资料用于验证交流流程，不代表完整正式角色设定。后续资料会以独立版本补全。
              </p>
            </section>
            <div class="metadata-row">
              <strong>剧情进度</strong
              ><span>{{ character.checkpointLabel }}</span
              ><button disabled title="剧情更新接口尚未实现">查看更新</button>
            </div></template
          >
          <template v-if="page === 'history'"
            ><small class="eyebrow">OUR CONVERSATIONS</small>
            <h1>聊过的那些事</h1>
            <p class="muted">从一句话，回到熟悉的交流。</p>
            <div class="filter-row">
              <button class="active" @click="loadSessions">全部角色</button
              ><span>{{ sessions.length }} 段对话</span>
            </div>
            <div v-if="historyLoading" class="empty">正在读取对话…</div>
            <div v-else-if="historyError" class="empty error">
              {{ historyError }}<button @click="loadSessions">重新加载</button>
            </div>
            <div v-else-if="!sessions.length" class="empty">
              <MessageCircle :size="30" />
              <h2>这里会留住你们的对话</h2>
              <p>发送第一条消息后，再回来看看。</p>
            </div>
            <button
              v-for="item in sessions"
              v-else
              :key="item.conversation_id"
              class="history-row"
              :disabled="
                !characters.some((c) => c.versionId === item.version_id)
              "
              @click="resume(item)"
            >
              <span class="history-initial">{{
                characters
                  .find((c) => c.versionId === item.version_id)
                  ?.name.slice(0, 1) || "旧"
              }}</span>
              <div>
                <strong>{{
                  characters.find((c) => c.versionId === item.version_id)
                    ?.name || "旧版测试角色"
                }}</strong>
                <p>{{ item.preview }}</p>
                <small>{{ item.turns }} 轮对话</small>
              </div>
              <MessageCircle :size="17" /></button
          ></template>
          <template v-if="page === 'settings'"
            ><small class="eyebrow">MAKE YOURSELF AT HOME</small>
            <h1>按你的习惯来</h1>
            <div class="settings-layout">
              <nav class="settings-nav">
                <button
                  v-for="(label, id) in {
                    general: '通用',
                    appearance: '外观',
                    voice: '声音',
                    data: '数据管理',
                  }"
                  :key="id"
                  :class="{ active: section === id }"
                  @click="section = id"
                >
                  {{ label }}
                </button>
              </nav>
              <div class="settings-content">
                <template v-if="section === 'general'"
                  ><h2>阅读与交流</h2>
                  <div class="setting-row">
                    <div>
                      <strong>聊天字体</strong>
                      <p>找到适合长时间阅读的大小。</p>
                    </div>
                    <div class="segmented">
                      <button
                        v-for="(label, id) in {
                          small: '小',
                          standard: '标准',
                          large: '大',
                        }"
                        :key="id"
                        :class="{ active: preferences.font === id }"
                        @click="preferences.font = id"
                      >
                        {{ label }}
                      </button>
                    </div>
                  </div>
                  <div class="setting-row">
                    <div>
                      <strong>发送方式</strong>
                      <p>Shift + Enter 始终可以换行。</p>
                    </div>
                    <select v-model="preferences.send" aria-label="发送方式">
                      <option value="enter">Enter</option>
                      <option value="ctrl">Ctrl / ⌘ + Enter</option>
                    </select>
                  </div>
                  <div class="setting-row">
                    <div>
                      <strong>界面动效</strong>
                      <p>角色展开与轻柔的过渡。</p>
                    </div>
                    <button
                      class="toggle"
                      role="switch"
                      :aria-checked="preferences.motion"
                      aria-label="界面动效"
                      :class="{ on: preferences.motion }"
                      @click="preferences.motion = !preferences.motion"
                    >
                      <span></span>
                    </button></div></template
                ><template v-if="section === 'appearance'"
                  ><h2>让相见更合心意</h2>
                  <div class="appearance-block">
                    <Portrait
                      :source="cover(character).source"
                      :crop="cover(character).crop.chat"
                      :name="character.name"
                    />
                    <div>
                      <h3>{{ character.name }}</h3>
                      <p class="muted">主题跟随当前角色变化。</p>
                      <button
                        class="primary"
                        :disabled="!connected"
                        @click="editing = true"
                      >
                        <ImagePlus :size="16" />更换封面
                      </button>
                      <div class="appearance-actions">
                        <button :disabled="!connected" @click="editing = true">
                          调整位置</button
                        ><button
                          :disabled="!connected"
                          @click="resetConfirm = true"
                        >
                          <RotateCcw :size="15" />恢复默认
                        </button>
                      </div>
                    </div>
                  </div>
                  <p class="muted fine-print">
                    封面与裁切仅保存在当前浏览器，按用户和角色分别保存。
                  </p></template
                ><template v-if="section === 'voice'"
                  ><h2>听见她的声音</h2>
                  <div class="feature-note">
                    <Volume2 :size="25" />
                    <p>语音尚未启用</p>
                    <span
                      >目前可以正常进行文字交流。声音资料和语音服务将在后续接入。</span
                    >
                  </div>
                  <div class="setting-row">
                    <div>
                      <strong>收到语音后</strong>
                      <p>提前保存偏好，接入语音后生效。</p>
                    </div>
                    <select
                      v-model="preferences.voice"
                      aria-label="语音播放方式"
                    >
                      <option value="manual">手动播放</option>
                      <option value="auto">自动播放</option>
                    </select>
                  </div></template
                ><template v-if="section === 'data'"
                  ><h2>与你有关的记录</h2>
                  <button class="setting-row link-row" @click="route('memory')">
                    <div>
                      <strong>个人记忆</strong>
                      <p>查看记忆功能的当前状态。</p>
                    </div>
                    <BookOpen :size="20" />
                  </button>
                  <div class="setting-row">
                    <div>
                      <strong>聊天记录</strong>
                      <p>保存在本机 PostgreSQL 中，刷新页面后仍可继续。</p>
                    </div>
                    <button @click="route('history')">查看历史</button>
                  </div>
                  <p class="fine-print muted">
                    当前为本地开发身份，暂不提供账号登录与跨设备同步。
                  </p></template
                >
              </div>
            </div></template
          >
          <template v-if="page === 'memory'"
            ><small class="eyebrow">WHAT SHE REMEMBERS</small>
            <h1>个人记忆</h1>
            <p class="muted">关于你的事，由你掌握。</p>
            <div class="empty memory-empty">
              <Sparkles :size="32" />
              <h2>个人记忆还未启用</h2>
              <p>
                聊天记录仍会正常保存。<br />记忆服务接入后，你可以在这里查看、纠正或删除保存的个人信息。
              </p>
              <button class="primary" @click="route('chat')">继续聊天</button>
            </div></template
          >
        </section>
      </main>
      <CoverEditor
        v-if="editing"
        :character="character"
        :value="cover(character)"
        @close="editing = false"
        @save="saveCover"
      />
      <div
        v-if="resetConfirm"
        class="modal-shade"
        @keydown.esc="resetConfirm = false"
      >
        <section
          class="modal small-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="reset-title"
        >
          <h2 id="reset-title">恢复 {{ character.name }} 的默认封面？</h2>
          <p class="muted">
            当前自定义图片与两个展示位置将被重置，聊天记录不受影响。
          </p>
          <footer>
            <button @click="resetConfirm = false">取消</button
            ><button class="primary" @click="resetCover">
              <Check :size="16" />恢复默认
            </button>
          </footer>
        </section>
      </div>
    </template>
  </div>
</template>
