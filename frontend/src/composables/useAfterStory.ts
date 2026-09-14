import {
  computed,
  nextTick,
  onMounted,
  onUnmounted,
  reactive,
  ref,
  watch,
  inject,
  provide,
} from "vue";
import type { InjectionKey } from "vue";
import { api, errorText } from "../api";
import { coverStorage } from "../storage";
import type {
  Character,
  Cover,
  History,
  Memory as PersonalMemory,
  MemoryPage,
  Session,
  SessionPage,
  Turn,
} from "../types";

export function createAfterStory() {
  const characters = ref<Character[]>([]);
  const selected = ref("nanally");
  const page = ref("home");
  const section = ref("general");
  const hovered = ref("nanally");
  const user = ref("");
  const connected = ref(false);
  const capabilities = reactive({ voice: false, memory: false });
  const busy = ref(false);
  const notice = ref("");
  const fatal = ref("");
  const editing = ref(false);
  const resetConfirm = ref(false);
  const covers = reactive<Record<string, Cover>>({});
  const sessions = ref<Session[]>([]);
  const historyLoading = ref(false);
  const historyError = ref("");
  const historyTotal = ref(0);
  const historyOffset = ref(0);
  const historyAppendFailed = ref(false);
  let historyRequest = 0;
  const memories = ref<PersonalMemory[]>([]);
  const memoryTotal = ref(0);
  const memoryLoading = ref(false);
  const memoryError = ref("");
  const memoryForm = ref(false);
  const memoryDraft = ref("");
  const memorySource = ref<string>();
  const memoryCreateRequest = ref("");
  const memoryEditing = ref<string>();
  const memorySaving = ref(false);
  const memoryDelete = ref<PersonalMemory>();
  let memoryRequest = 0;
  const targetTurn = ref("");
  const scrollArea = ref<HTMLElement>();
  const preferences = reactive({
    font: "standard",
    send: "enter",
    motion: true,
    voice: "manual",
  });
  type Chat = {
    id: string;
    session?: Session;
    turns: Turn[];
    total: number;
    offset: number;
    draft: string;
    loading: boolean;
    sending: boolean;
    error: string;
    revision: number;
    pending?: { request_id: string; text: string };
  };
  const chats = reactive<Record<string, Chat>>({});
  const conversations = reactive<Record<string, Chat>>({});
  const opening: Record<string, number> = {};
  const character = computed(
    () =>
      characters.value.find((c) => c.id === selected.value) ||
      characters.value[0],
  );
  const chat = computed(() => chats[selected.value]);
  const legacyVersion = computed(
    () =>
      !!chat.value?.session &&
      chat.value.session.version_id !== character.value?.versionId,
  );
  // Never display the previous instance's memories while switching or recovering metadata.
  watch(
    () => [selected.value, chat.value?.session?.instance_id],
    () => {
      ++memoryRequest;
      memories.value = [];
      memoryTotal.value = 0;
      memoryError.value = "";
      memoryLoading.value = false;
    },
    { flush: "sync" },
  );
  watch(
    () => [selected.value, chat.value?.id],
    () => {
      cancelMemoryForm();
      memoryEditing.value = undefined;
      memoryDelete.value = undefined;
    },
    { flush: "sync" },
  );
  function displayTime(value: string | null | undefined) {
    if (!value || Number.isNaN(Date.parse(value))) return "未记录时间";
    return new Intl.DateTimeFormat("zh-CN", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  }
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
  function saveChat(id: string, state = chats[id]) {
    if (state) {
      const saved = {
        id: state.id,
        session: state.session,
        draft: state.draft,
        pending: state.pending,
      };
      if (state.id) store(`conversation:${state.id}`, saved);
      if (chats[id] === state) store(`draft:${id}`, saved);
    }
  }
  function route(next: string, conversationId?: string, turnId?: string) {
    const params = new URLSearchParams();
    if (next === "chat" && (conversationId || chat.value?.id))
      params.set("conversation", conversationId || chat.value!.id);
    if (next === "chat" && turnId) params.set("turn", turnId);
    const hash = `#/${next}/${selected.value}${params.size ? `?${params}` : ""}`;
    if (location.hash === hash) routeChanged();
    else location.hash = hash;
  }
  function routeChanged() {
    const [path, query] = location.hash.split("?");
    const [, next, id] = (path || "").split("/");
    const params = new URLSearchParams(query);
    page.value = [
      "home",
      "chat",
      "characters",
      "profile",
      "history",
      "settings",
      "memory",
    ].includes(next || "")
      ? next!
      : "home";
    if (characters.value.some((c) => c.id === id)) selected.value = id!;
    targetTurn.value = page.value === "chat" ? params.get("turn") || "" : "";
    if (
      connected.value &&
      ["home", "chat", "profile", "memory"].includes(page.value)
    )
      void openChat(
        selected.value,
        params.get("conversation") || undefined,
        targetTurn.value || undefined,
      );
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
      const result = await api<{
        user_id: string;
        capabilities?: { voice?: boolean; memory?: boolean };
      }>("/health");
      user.value = result.user_id;
      Object.assign(capabilities, result.capabilities || {});
      Object.assign(preferences, read("preferences", preferences));
      if (!location.hash) selected.value = read("selected", selected.value);
      for (const c of characters.value) {
        const saved = read<{
          id?: string;
          draft: string;
          pending?: Chat["pending"];
          session?: Session;
        }>(`draft:${c.id}`, { draft: "" });
        chats[c.id] = {
          id: saved.id || "",
          turns: [],
          total: 0,
          offset: 0,
          draft: saved.draft,
          pending: saved.pending,
          session: saved.session,
          loading: false,
          sending: false,
          error: "",
          revision: 0,
        };
        if (saved.id) conversations[saved.id] = chats[c.id]!;
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
  async function refresh(
    id: string,
    older = false,
    state = chats[id]!,
    aroundTurnId?: string,
  ) {
    if (!state.id) return;
    const revision = ++state.revision;
    const conversationId = state.id;
    let offset = older ? Math.max(0, state.offset - 30) : 0;
    if (!older && !aroundTurnId) {
      const count = await api<History>(
        `/conversations/${encodeURIComponent(conversationId)}/messages?limit=1`,
      );
      if (revision !== state.revision) return;
      offset = Math.max(0, count.total - 30);
    }
    const params = new URLSearchParams({ offset: String(offset), limit: "30" });
    if (aroundTurnId) params.set("around_turn_id", aroundTurnId);
    const result = await api<History>(
      `/conversations/${encodeURIComponent(conversationId)}/messages?${params}`,
    );
    if (revision !== state.revision || conversationId !== state.id) return;
    state.turns = older
      ? [
          ...result.turns.filter(
            (t) => !state.turns.some((old) => old.turn_id === t.turn_id),
          ),
          ...state.turns,
        ]
      : result.turns;
    state.total = result.total;
    state.offset = result.offset;
    if (
      state.pending &&
      state.turns.some(
        (t) =>
          t.request_id === state.pending?.request_id &&
          t.status === "completed",
      )
    ) {
      state.pending = undefined;
      saveChat(id, state);
    }
    if (state.pending && !state.sending)
      state.error = "有一条尚未完成的消息，点击重试继续发送。";
    if (!older) {
      await nextTick();
      if (
        id === selected.value &&
        chats[id] === state &&
        page.value === "chat"
      ) {
        if (aroundTurnId) {
          document
            .getElementById(`turn-${aroundTurnId}`)
            ?.scrollIntoView({ block: "center" });
        } else
          scrollArea.value?.scrollTo({ top: scrollArea.value.scrollHeight });
      }
    }
  }
  async function openChat(
    id: string,
    conversationId?: string,
    aroundTurnId?: string,
  ) {
    let state = chats[id];
    const c = characters.value.find((item) => item.id === id);
    if (!state || !c) return;
    if (conversationId && conversationId !== state.id) {
      saveChat(id, state);
      const saved = read<Partial<Chat>>(`conversation:${conversationId}`, {});
      state =
        conversations[conversationId] ||
        reactive<Chat>({
          id: conversationId,
          session: saved.session,
          draft: saved.id === conversationId ? saved.draft || "" : "",
          pending: saved.id === conversationId ? saved.pending : undefined,
          turns: [],
          total: 0,
          offset: 0,
          loading: false,
          sending: false,
          error: "",
          revision: 0,
        });
      conversations[conversationId] = state;
      chats[id] = state;
    }
    const request = (opening[id] || 0) + 1;
    opening[id] = request;
    if (state.sending) return;
    state.loading = true;
    state.error = "";
    state.session = undefined;
    try {
      if (!state.id)
        state.id = (
          await api<{ conversation_id: string }>("/sessions/open", {
            version_id: c.versionId,
          })
        ).conversation_id;
      if (opening[id] !== request || chats[id] !== state) return;
      const session = await api<Session>(
        `/conversations/${encodeURIComponent(state.id)}`,
      );
      if (opening[id] !== request || chats[id] !== state) return;
      if (session.character_id !== id || session.conversation_id !== state.id)
        throw new Error("conversation_identity_mismatch");
      state.session = session;
      conversations[state.id] = state;
      saveChat(id, state);
      await refresh(id, false, state, aroundTurnId);
      if (
        ["home", "memory"].includes(page.value) &&
        capabilities.memory &&
        chats[id] === state &&
        id === selected.value
      )
        await loadMemories(session.instance_id);
    } catch (error) {
      if (opening[id] === request && chats[id] === state)
        state.error = errorText(error);
    } finally {
      if (opening[id] === request) state.loading = false;
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
      !state.session ||
      (!retry && (!state.draft.trim() || state.pending))
    )
      return;
    const pending = retry || {
      request_id: crypto.randomUUID(),
      text: state.draft.trim(),
    };
    state.pending = pending;
    if (!retry) state.draft = "";
    saveChat(id, state);
    state.sending = true;
    state.error = "";
    try {
      await api(
        `/conversations/${encodeURIComponent(state.id)}/messages`,
        pending,
      );
      state.pending = undefined;
      saveChat(id, state);
      await refresh(id, false, state);
    } catch (error) {
      state.error = errorText(error);
      try {
        await refresh(id, false, state);
      } catch {
        /* Keep the durable outbox when offline. */
      }
    } finally {
      state.sending = false;
    }
  }
  async function retryChat() {
    const id = selected.value;
    const state = chats[id];
    if (!state || state.sending || state.loading) return;
    if (!state.session) {
      const pending = state.pending;
      await openChat(id, state.id || undefined, targetTurn.value || undefined);
      if (chats[id] === state && state.session && pending === state.pending)
        await send(pending);
      return;
    }
    if (state.pending) await send(state.pending);
    else
      await openChat(id, state.id || undefined, targetTurn.value || undefined);
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
    const area = scrollArea.value;
    const oldHeight = area?.scrollHeight || 0;
    const oldTop = area?.scrollTop || 0;
    state.loading = true;
    try {
      await refresh(selected.value, true, state);
      await nextTick();
      if (area && area === scrollArea.value && chat.value === state)
        area.scrollTop = oldTop + area.scrollHeight - oldHeight;
    } catch (error) {
      state.error = errorText(error);
    } finally {
      state.loading = false;
    }
  }
  watch(
    () => chat.value?.pending?.request_id,
    async (pending) => {
      if (!pending || page.value !== "chat") return;
      await nextTick();
      scrollArea.value?.scrollTo({ top: scrollArea.value.scrollHeight });
    },
  );
  async function loadSessions(append = false) {
    if (append && historyLoading.value) return;
    const request = ++historyRequest;
    historyLoading.value = true;
    historyError.value = "";
    historyAppendFailed.value = append;
    try {
      const result = await api<SessionPage>(
        `/history?offset=${append ? historyOffset.value : 0}&limit=20`,
      );
      if (request !== historyRequest) return;
      sessions.value = append
        ? [
            ...sessions.value,
            ...result.items.filter(
              (item) =>
                !sessions.value.some(
                  (existing) =>
                    existing.conversation_id === item.conversation_id,
                ),
            ),
          ]
        : result.items;
      historyTotal.value = result.total;
      historyOffset.value = result.offset + result.items.length;
    } catch (error) {
      if (request === historyRequest) historyError.value = errorText(error);
    } finally {
      if (request === historyRequest) historyLoading.value = false;
    }
  }
  async function loadMemories(instanceId = chat.value?.session?.instance_id) {
    if (!instanceId || !capabilities.memory) return;
    const request = ++memoryRequest;
    memoryLoading.value = true;
    memoryError.value = "";
    try {
      const result = await api<MemoryPage>(
        `/instances/${encodeURIComponent(instanceId)}/memories?limit=100`,
      );
      if (
        request !== memoryRequest ||
        instanceId !== chat.value?.session?.instance_id
      )
        return;
      memories.value = result.items;
      memoryTotal.value = result.total;
    } catch (error) {
      if (request === memoryRequest) memoryError.value = errorText(error);
    } finally {
      if (request === memoryRequest) memoryLoading.value = false;
    }
  }
  function beginMemory(content = "", sourceMessageId?: string) {
    memoryEditing.value = undefined;
    memoryDraft.value = content;
    memorySource.value = sourceMessageId;
    memoryCreateRequest.value = crypto.randomUUID();
    memoryForm.value = true;
    if (page.value !== "memory") route("memory");
  }
  function cancelMemoryForm() {
    memoryForm.value = false;
    memoryDraft.value = "";
    memorySource.value = undefined;
    memoryCreateRequest.value = "";
  }
  async function createMemory() {
    const instanceId = chat.value?.session?.instance_id;
    const content = memoryDraft.value.trim();
    if (!instanceId || !content || memorySaving.value) return;
    memorySaving.value = true;
    memoryError.value = "";
    try {
      await api(
        `/instances/${encodeURIComponent(instanceId)}/memories`,
        {
          request_id: memoryCreateRequest.value || crypto.randomUUID(),
          content,
          source_message_id: memorySource.value,
        },
        "POST",
      );
      cancelMemoryForm();
      notice.value = "已加入个人记忆。";
      await loadMemories(instanceId);
    } catch (error) {
      memoryError.value = errorText(error);
    } finally {
      memorySaving.value = false;
    }
  }
  function editMemory(memory: PersonalMemory) {
    memoryForm.value = false;
    memoryEditing.value = memory.memory_id;
    memoryDraft.value = memory.content;
  }
  async function saveMemory(memory: PersonalMemory) {
    const content = memoryDraft.value.trim();
    if (!content || memorySaving.value) return;
    memorySaving.value = true;
    memoryError.value = "";
    try {
      await api(
        `/memories/${encodeURIComponent(memory.memory_id)}`,
        { expected_revision: memory.revision, content },
        "PATCH",
      );
      memoryEditing.value = undefined;
      memoryDraft.value = "";
      notice.value = "记忆已更正。";
      await loadMemories();
    } catch (error) {
      memoryError.value = errorText(error);
    } finally {
      memorySaving.value = false;
    }
  }
  async function confirmDeleteMemory() {
    const target = memoryDelete.value;
    if (!target || memorySaving.value) return;
    memorySaving.value = true;
    memoryError.value = "";
    try {
      await api(
        `/memories/${encodeURIComponent(target.memory_id)}?expected_revision=${target.revision}`,
        undefined,
        "DELETE",
      );
      memoryDelete.value = undefined;
      notice.value = "这条记忆已删除，原聊天仍会保留。";
      await loadMemories();
    } catch (error) {
      memoryError.value = errorText(error);
    } finally {
      memorySaving.value = false;
    }
  }
  function resume(item: Session, turnId?: string) {
    const c = characters.value.find((c) => c.id === item.character_id);
    if (!c) return;
    selected.value = c.id;
    store("selected", c.id);
    route("chat", item.conversation_id, turnId);
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
    () => editing.value || resetConfirm.value || !!memoryDelete.value,
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
    if (!editing.value && !resetConfirm.value && !memoryDelete.value) return;
    if (event.key === "Escape") {
      editing.value = false;
      resetConfirm.value = false;
      memoryDelete.value = undefined;
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

  return {
    characters,
    selected,
    page,
    section,
    hovered,
    user,
    connected,
    capabilities,
    busy,
    notice,
    fatal,
    editing,
    resetConfirm,
    covers,
    sessions,
    historyLoading,
    historyError,
    historyTotal,
    historyOffset,
    historyAppendFailed,
    historyRequest,
    memories,
    memoryTotal,
    memoryLoading,
    memoryError,
    memoryForm,
    memoryDraft,
    memorySource,
    memoryCreateRequest,
    memoryEditing,
    memorySaving,
    memoryDelete,
    memoryRequest,
    targetTurn,
    scrollArea,
    preferences,
    chats,
    conversations,
    opening,
    character,
    chat,
    legacyVersion,
    displayTime,
    theme,
    key,
    cover,
    store,
    saveChat,
    route,
    routeChanged,
    choose,
    connect,
    refresh,
    openChat,
    send,
    retryChat,
    inputKey,
    recoverDraft,
    loadOlder,
    loadSessions,
    loadMemories,
    beginMemory,
    cancelMemoryForm,
    createMemory,
    editMemory,
    saveMemory,
    confirmDeleteMemory,
    resume,
    saveCover,
    resetCover,
    previousFocus,
    modalKeys,
  };
}

const stateKey: InjectionKey<ReturnType<typeof createAfterStory>> =
  Symbol("AfterStory");
export function provideAfterStory(state: ReturnType<typeof createAfterStory>) {
  provide(stateKey, state);
}
export function useAfterStory() {
  const state = inject(stateKey);
  if (!state) throw new Error("AfterStory state is unavailable");
  return state;
}
