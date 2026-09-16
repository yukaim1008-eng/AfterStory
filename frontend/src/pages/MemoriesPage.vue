<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  BookHeart,
  LoaderCircle,
  MessageCircle,
  Search,
} from "lucide-vue-next";
import { useAfterStory } from "../composables/useAfterStory";
import CharacterAvatar from "../components/CharacterAvatar.vue";
import MemoryCollection from "../components/MemoryCollection.vue";
import { displayTime, excerpt } from "../presentation";

const {
  page,
  character,
  characters,
  cover,
  sessions,
  historyLoading,
  historyError,
  historyTotal,
  historyOffset,
  historyAppendFailed,
  route,
  loadSessions,
  resume,
} = useAfterStory();

const characterFilter = ref("all");
const timeFilter = ref("all");
const query = ref("");
let filterToken = 0;

const filtersActive = computed(
  () =>
    characterFilter.value !== "all" ||
    timeFilter.value !== "all" ||
    !!query.value.trim(),
);

const matchesTime = (value: string | null) => {
  if (timeFilter.value === "all") return true;
  if (!value || Number.isNaN(Date.parse(value)))
    return timeFilter.value === "unknown";
  const age = Date.now() - Date.parse(value);
  return timeFilter.value === "week"
    ? age <= 7 * 86400000
    : timeFilter.value === "month"
      ? age <= 31 * 86400000
      : false;
};

const filteredSessions = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase();
  return sessions.value.filter((item) => {
    const found = characters.value.find(
      (candidate) => candidate.id === item.character_id,
    );
    return (
      (characterFilter.value === "all" ||
        item.character_id === characterFilter.value) &&
      matchesTime(item.last_activity_at) &&
      (!needle ||
        `${item.preview} ${found?.name || item.name}`
          .toLocaleLowerCase()
          .includes(needle))
    );
  });
});

function installedCharacter(id: string) {
  return characters.value.find((item) => item.id === id);
}

function isLegacy(item: (typeof sessions.value)[number]) {
  const installed = installedCharacter(item.character_id);
  return !!installed && installed.versionId !== item.version_id;
}

watch(
  [characterFilter, timeFilter, query],
  async () => {
    const token = ++filterToken;
    if (!filtersActive.value) return;
    while (historyOffset.value < historyTotal.value && !historyError.value) {
      const before = historyOffset.value;
      await loadSessions(true);
      if (token !== filterToken || historyOffset.value <= before) return;
    }
  },
  { flush: "post" },
);
</script>

<template>
  <main
    v-if="character"
    id="main-content"
    tabindex="-1"
    class="memories-workspace"
  >
    <section class="memories-content">
      <header class="memories-hero">
        <div>
          <small>OUR MEMORIES</small>
          <h1>与你的回忆 <BookHeart :size="31" /></h1>
          <p>那些聊过的瞬间，和你主动留下的珍贵小事。</p>
        </div>
        <div class="hero-aside">
          <span>有些话说完了，<br />但不会真的消失。</span>
          <CharacterAvatar :character="character" :cover="cover(character)" />
        </div>
      </header>

      <div class="memory-tabs" role="tablist" aria-label="回忆类别">
        <button
          role="tab"
          :aria-selected="page === 'history'"
          :class="{ active: page === 'history' }"
          @click="route('history')"
        >
          <MessageCircle :size="18" />聊天片段
        </button>
        <button
          role="tab"
          :aria-selected="page === 'memory'"
          :class="{ active: page === 'memory' }"
          @click="route('memory')"
        >
          <BookHeart :size="18" />她记得的事
        </button>
      </div>

      <MemoryCollection v-if="page === 'memory'" />
      <section v-else class="history-collection" aria-label="聊天片段">
        <div class="history-controls">
          <div class="character-chips" aria-label="筛选角色">
            <button
              :class="{ active: characterFilter === 'all' }"
              @click="characterFilter = 'all'"
            >
              全部
            </button>
            <button
              v-for="item in characters"
              :key="item.id"
              :class="{ active: characterFilter === item.id }"
              @click="characterFilter = item.id"
            >
              <CharacterAvatar :character="item" :cover="cover(item)" />{{
                item.name
              }}
            </button>
          </div>
          <select v-model="timeFilter" aria-label="筛选时间">
            <option value="all">全部时间</option>
            <option value="week">最近一周</option>
            <option value="month">最近一个月</option>
            <option value="unknown">未记录时间</option>
          </select>
          <label class="search-control">
            <Search :size="17" />
            <input
              v-model="query"
              type="search"
              aria-label="搜索回忆"
              placeholder="搜索回忆…"
            />
          </label>
          <span>匹配 {{ filteredSessions.length }} 段</span>
        </div>

        <div class="history-scroll">
          <div v-if="historyLoading && !sessions.length" class="empty">
            <LoaderCircle class="spin" :size="24" />正在读取对话…
          </div>
          <div v-if="historyError" class="history-error" role="alert">
            {{ historyError }}
            <button
              :disabled="historyLoading"
              @click="loadSessions(historyAppendFailed)"
            >
              重新加载
            </button>
          </div>
          <div
            v-if="!historyLoading && !historyError && !sessions.length"
            class="empty"
          >
            <MessageCircle :size="30" />
            <h2>这里会留住你们的对话</h2>
            <p>第一段回忆，还在等你们一起写下。</p>
            <button class="empty-action" @click="route('chat')">
              去开始聊天
            </button>
          </div>
          <div
            v-else-if="sessions.length && !filteredSessions.length"
            class="empty"
          >
            <Search :size="28" />
            <h2>没有找到匹配的回忆</h2>
            <p>换一个角色、时间或关键词试试。</p>
          </div>

          <div v-else class="history-grid">
            <button
              v-for="item in filteredSessions"
              :key="item.conversation_id"
              class="history-row"
              :data-version="item.version_id"
              :data-conversation="item.conversation_id"
              :disabled="!installedCharacter(item.character_id)"
              @click="resume(item)"
            >
              <CharacterAvatar
                v-if="installedCharacter(item.character_id)"
                :character="installedCharacter(item.character_id)!"
                :cover="cover(installedCharacter(item.character_id)!)"
              />
              <span v-else class="missing-avatar">?</span>
              <div>
                <span class="card-meta">
                  <time :datetime="item.last_activity_at || undefined">{{
                    displayTime(item.last_activity_at)
                  }}</time>
                  <span>聊天片段</span>
                </span>
                <h2>{{ excerpt(item.preview || "还没有消息", 34) }}</h2>
                <p>{{ item.preview || "这段相见还没有留下文字。" }}</p>
                <footer>
                  <strong>{{
                    installedCharacter(item.character_id)?.name || item.name
                  }}</strong>
                  <span>{{ item.turns }} 轮对话</span
                  ><span class="continue-reading">看看那天聊了什么 →</span>
                  <span v-if="isLegacy(item)">早些时候的相见</span>
                  <span v-if="!installedCharacter(item.character_id)"
                    >角色暂不可用</span
                  >
                </footer>
              </div>
            </button>
          </div>

          <button
            v-if="!filtersActive && historyOffset < historyTotal"
            class="load-older"
            :disabled="historyLoading"
            @click="loadSessions(true)"
          >
            {{ historyLoading ? "正在读取…" : "加载更多对话" }}
          </button>
        </div>
      </section>
    </section>
  </main>
</template>

<style scoped>
.memories-workspace {
  width: 100%;
  max-width: 1500px;
  height: calc(
    100dvh - var(--desktop-header-height) - 2 * var(--page-padding-y)
  );
  min-height: 0;
  margin: var(--page-padding-y) auto;
  overflow: hidden;
  border: 1px solid #ffffffba;
  border-radius: var(--radius-panel);
  background: linear-gradient(
    145deg,
    #ffffffaa,
    color-mix(in srgb, var(--soft) 26%, #ffffff75)
  );
  box-shadow: var(--shadow-panel);
}
.memories-content {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0 26px 20px;
  background: transparent;
}
.memories-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  min-height: 90px;
  margin: 0 -26px;
  padding: 12px 26px;
  background: linear-gradient(
    100deg,
    #ffffff72,
    color-mix(in srgb, var(--soft) 42%, transparent)
  );
}
.memories-hero small {
  color: var(--muted);
  font-size: 10px;
  letter-spacing: 5px;
}
.memories-hero h1 {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 5px 0;
  color: var(--text);
  font-size: clamp(32px, 2.6vw, 42px);
}
.memories-hero h1 svg {
  color: var(--accent);
  transform: rotate(-12deg);
}
.memories-hero p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}
.hero-aside {
  display: flex;
  align-items: center;
  gap: 14px;
  color: var(--muted);
  font-family: "Kaiti SC", "STKaiti", "KaiTi", serif;
  font-size: 13px;
  text-align: right;
  transform: rotate(-2deg);
}
.memories-hero .character-avatar {
  width: 48px;
  height: 48px;
  box-shadow: 0 12px 34px color-mix(in srgb, var(--accent) 18%, transparent);
}
.memory-tabs {
  flex-shrink: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  max-width: 420px;
  margin: 12px 0;
  padding: 3px;
  border: 1px solid #ffffffb5;
  border-radius: 14px;
  background: #ffffff72;
}
.memory-tabs button {
  justify-content: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 11px;
  color: var(--muted);
}
.memory-tabs button.active {
  background: color-mix(in srgb, var(--soft) 70%, white);
  color: var(--accent) !important;
}
.history-controls {
  flex-shrink: 0;
  display: grid;
  grid-template-columns: minmax(260px, auto) auto minmax(190px, 1fr) auto;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.history-collection {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.history-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 4px 4px 8px;
  overscroll-behavior: contain;
}
.character-chips {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  overflow: hidden;
}
.character-chips button {
  padding: 5px 8px;
  border-radius: 99px;
  color: var(--muted);
  font-size: 11px;
  white-space: nowrap;
}
.character-chips button.active {
  background: color-mix(in srgb, var(--soft) 72%, white);
  color: var(--accent);
}
.character-chips .character-avatar {
  width: 20px;
  height: 20px;
  margin-right: 4px;
}
.history-controls select,
.search-control {
  min-width: 0;
  padding: 8px 11px;
  border: 1px solid var(--soft);
  border-radius: 99px;
  background: #ffffffa8;
  color: var(--text);
}
.search-control {
  display: flex;
  align-items: center;
  gap: 8px;
}
.search-control input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
}
.history-controls > span {
  color: var(--muted);
  font-size: 11px;
}
.history-error {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin: 12px 0;
  padding: 12px 16px;
  border-radius: 12px;
  background: color-mix(in srgb, var(--soft) 60%, white);
  color: var(--accent);
}
.history-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0;
}
.history-row {
  box-sizing: border-box;
  display: grid;
  grid-template-columns: 46px minmax(0, 1fr);
  align-items: stretch;
  width: 100%;
  min-width: 0;
  margin: 0;
  padding: 13px 10px;
  border: 0;
  border-bottom: 1px solid color-mix(in srgb, var(--soft) 55%, transparent);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  text-align: left;
}
.history-row::after {
  content: none;
}
.history-row:hover:not(:disabled) {
  transform: none;
  background: color-mix(in srgb, var(--soft) 24%, transparent);
}
.history-row .character-avatar,
.missing-avatar {
  width: 34px;
  height: 34px;
  min-height: 34px;
  border-radius: 50%;
}
.missing-avatar {
  display: grid;
  place-items: center;
  background: var(--soft);
  color: var(--muted);
}
.history-row > div {
  min-width: 0;
}
.card-meta,
.history-row footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  font-size: 10px;
}
.card-meta > span {
  padding: 3px 8px;
  border-radius: 99px;
  background: var(--soft);
  color: var(--accent);
}
.history-row h2 {
  margin: 9px 0 6px;
  color: var(--text);
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.history-row p {
  display: -webkit-box;
  margin: 0 0 12px;
  overflow: hidden;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.7;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
.history-row footer strong {
  color: var(--text);
}
.continue-reading {
  margin-left: auto;
  color: var(--accent);
}
.empty-action {
  margin-top: 8px;
  color: var(--accent);
  font-size: 12px;
}
.load-older {
  display: flex;
  margin: 20px auto 0;
  padding: 10px 20px;
  border: 1px solid var(--soft);
  border-radius: 99px;
  color: var(--accent);
}
@media (min-width: 1750px) {
  .history-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 900px) {
  .workspace.memories-workspace {
    grid-template-columns: 190px minmax(0, 1fr);
  }
  .history-controls {
    grid-template-columns: 1fr 1fr;
  }
  .history-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 700px) {
  .workspace.memories-workspace {
    grid-template-columns: 1fr;
    height: calc(100dvh - 78px);
    min-height: 500px;
  }
  .memories-content {
    padding-inline: 18px;
  }
  .memories-hero {
    margin-inline: -18px;
    padding-inline: 18px;
  }
  .memories-hero .character-avatar {
    display: none;
  }
  .history-controls {
    grid-template-columns: 1fr;
  }
}
</style>
