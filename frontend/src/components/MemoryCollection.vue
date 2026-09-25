<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  LoaderCircle,
  MoreHorizontal,
  Pencil,
  Plus,
  Sparkles,
  Trash2,
} from "lucide-vue-next";
import { useAfterStory } from "../composables/useAfterStory";
import { displayTime, excerpt } from "../presentation";

const {
  characters,
  selected,
  chat,
  capabilities,
  memories,
  memoryTotal,
  memoryOffset,
  memoryLoading,
  memoryError,
  memoryForm,
  memoryDraft,
  memorySource,
  memoryEditing,
  memorySaving,
  memoryDelete,
  matters,
  matterLoading,
  matterError,
  matterForm,
  matterContent,
  matterWhen,
  dueReminder,
  store,
  route,
  beginMemory,
  cancelMemoryForm,
  createMemory,
  editMemory,
  saveMemory,
  confirmDeleteMemory,
  loadMemories,
  createMatter,
  closeMatter,
  dismissDueReminder,
} = useAfterStory();

const query = ref("");
const timeFilter = ref("all");
const typeFilter = ref("all");
const view = ref<"memory" | "matters">("memory");
const openMenu = ref<string>();
const selectedCharacter = computed(() =>
  characters.value.find((item) => item.id === selected.value),
);

function memoryTitle(content: string) {
  return excerpt(content.split(/\n\s*\n/)[0] || content, 34);
}

function memoryDetail(content: string) {
  const parts = content.split(/\n\s*\n/).filter(Boolean);
  return parts.length > 1 ? parts.slice(1).join("\n\n") : "";
}

const matchesTime = (value: string) => {
  if (timeFilter.value === "all") return true;
  const date = Date.parse(value);
  if (Number.isNaN(date)) return timeFilter.value === "unknown";
  const age = Date.now() - date;
  return timeFilter.value === "week"
    ? age <= 7 * 86400000
    : timeFilter.value === "month"
      ? age <= 31 * 86400000
      : false;
};

const filtered = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase();
  return memories.value.filter((item) => {
    const typeMatches =
      typeFilter.value === "all" || item.memory_type === typeFilter.value;
    return (
      typeMatches &&
      matchesTime(item.updated_at) &&
      (!needle || item.content.toLocaleLowerCase().includes(needle))
    );
  });
});

function switchCharacter(event: Event) {
  const id = (event.target as HTMLSelectElement).value;
  if (!characters.value.some((item) => item.id === id)) return;
  selected.value = id;
  store("selected", id);
  route("memory");
}

function cancelEdit() {
  memoryEditing.value = undefined;
  memoryDraft.value = "";
}

function loadMore() {
  return (
    loadMemories as (instanceId?: string, append?: boolean) => Promise<void>
  )(undefined, true);
}

watch(selected, () => {
  timeFilter.value = "all";
  typeFilter.value = "all";
  openMenu.value = undefined;
});
</script>

<template>
  <section class="memory-collection" aria-label="她记得的事">
    <header class="collection-intro">
      <p>她认真留下的事，也可以随时更正或删除。</p>
    </header>

    <div class="collection-toolbar">
      <div class="collection-switch" role="tablist" aria-label="记忆内容">
        <button :class="{ active: view === 'memory' }" @click="view = 'memory'">
          长期记忆
        </button>
        <button
          :class="{ active: view === 'matters' }"
          @click="view = 'matters'"
        >
          持续事项
        </button>
      </div>
      <div v-if="view === 'memory'" class="collection-filters">
        <select
          :value="selected"
          aria-label="筛选角色"
          @change="switchCharacter"
        >
          <option v-for="item in characters" :key="item.id" :value="item.id">
            {{ item.name }}
          </option>
        </select>
        <select v-model="timeFilter" aria-label="筛选时间">
          <option value="all">全部时间</option>
          <option value="week">最近一周</option>
          <option value="month">最近一个月</option>
          <option value="unknown">未记录时间</option>
        </select>
        <select v-model="typeFilter" aria-label="筛选类型">
          <option value="all">全部类型</option>
          <option value="fact">事实</option>
          <option value="preference">偏好</option>
          <option value="event">经历</option>
        </select>
        <label class="memory-search">
          <input
            v-model="query"
            type="search"
            aria-label="搜索回忆"
            placeholder="搜索回忆…"
          />
        </label>
      </div>
      <button
        v-if="capabilities.memory && view === 'memory'"
        class="primary add-memory"
        :disabled="memorySaving || !chat?.session"
        @click="beginMemory()"
      >
        <Plus :size="16" />添加一条记忆
      </button>
    </div>

    <div class="collection-scroll">
      <aside v-if="dueReminder" class="due-reminder" role="status">
        <div>
          <strong>约定的提醒</strong>
          <p>{{ dueReminder.content }}</p>
        </div>
        <button class="primary" @click="dismissDueReminder">我知道了</button>
      </aside>

      <template v-if="view === 'matters'">
        <form
          v-if="matterForm"
          class="memory-form"
          @submit.prevent="createMatter"
        >
          <label for="matter-content">希望她之后继续记得什么？</label>
          <textarea
            id="matter-content"
            v-model="matterContent"
            maxlength="2000"
            rows="3"
          ></textarea>
          <label for="matter-when">站内提醒时间（可留空）</label>
          <input id="matter-when" v-model="matterWhen" type="datetime-local" />
          <small
            >留空时只作为持续事项；填写明确时间后，会在下次打开 AfterStory
            时补发站内提醒。</small
          >
          <footer>
            <button type="button" @click="matterForm = false">取消</button>
            <button
              class="primary"
              :disabled="memorySaving || !matterContent.trim()"
            >
              保存事项
            </button>
          </footer>
        </form>
        <div v-if="matterError" class="memory-error" role="alert">
          {{ matterError }}
        </div>
        <div v-if="matterLoading" class="empty">
          <LoaderCircle class="spin" :size="24" />
        </div>
        <div
          v-else-if="!matters.length && !matterForm"
          class="empty memory-empty"
        >
          <Sparkles :size="30" />
          <h2>还没有持续事项</h2>
          <p>可以记下一件以后继续聊、继续做或需要提醒的事。</p>
          <button class="primary" @click="matterForm = true">
            添加持续事项
          </button>
        </div>
        <template v-else>
          <button
            v-if="!matterForm"
            class="primary add-matter"
            @click="matterForm = true"
          >
            <Plus :size="16" />添加持续事项
          </button>
          <div class="memory-list matter-list">
            <article v-for="item in matters" :key="item.matter_id">
              <header>
                <span>{{
                  item.status === "open"
                    ? "进行中"
                    : item.status === "completed"
                      ? "已完成"
                      : "已取消"
                }}</span
                ><time>{{ displayTime(item.scheduled_at) }}</time>
              </header>
              <h3>{{ item.content }}</h3>
              <p v-if="item.next_step">下一步：{{ item.next_step }}</p>
              <footer v-if="item.status === 'open'">
                <span></span
                ><button @click="closeMatter(item, 'complete')">完成</button
                ><button @click="closeMatter(item, 'cancel')">取消事项</button>
              </footer>
            </article>
          </div>
        </template>
      </template>

      <template v-else>
        <div v-if="!capabilities.memory" class="empty memory-empty">
          <Sparkles :size="32" />
          <h2>个人记忆还未启用</h2>
          <p>
            聊天记录仍会正常保存。<br />记忆服务接入后，你可以在这里查看、纠正或删除保存的个人信息。
          </p>
          <button class="primary" @click="route('chat')">继续聊天</button>
        </div>

        <template v-else>
          <form
            v-if="memoryForm"
            class="memory-form"
            @submit.prevent="createMemory"
          >
            <label for="new-memory">希望她记住什么？</label>
            <textarea
              id="new-memory"
              v-model="memoryDraft"
              maxlength="2000"
              rows="4"
              placeholder="例如：我习惯在晚上散步。"
            ></textarea>
            <small v-if="memorySource"
              >这段内容来自你选择的一条聊天消息。</small
            >
            <footer>
              <button
                type="button"
                :disabled="memorySaving"
                @click="cancelMemoryForm"
              >
                取消
              </button>
              <button
                class="primary"
                :disabled="
                  memorySaving || !chat?.session || !memoryDraft.trim()
                "
              >
                {{ memorySaving ? "保存中…" : "保存" }}
              </button>
            </footer>
          </form>

          <div v-if="memoryError" class="memory-error" role="alert">
            {{ memoryError }}
            <button
              :disabled="memoryLoading"
              @click="
                memories.length < memoryTotal ? loadMore() : loadMemories()
              "
            >
              刷新
            </button>
          </div>
          <div v-if="memoryLoading && !memories.length" class="empty">
            <LoaderCircle class="spin" :size="24" />
            <p>正在读取个人记忆…</p>
          </div>
          <div
            v-else-if="!memories.length && !memoryForm"
            class="empty memory-empty"
          >
            <Sparkles :size="30" />
            <h2>她还没有留下特别的记忆</h2>
            <p>聊得久一点，<br />有些事情会慢慢留在这里。</p>
            <button
              class="primary"
              :disabled="memorySaving || !chat?.session"
              @click="beginMemory()"
            >
              添加第一条记忆
            </button>
          </div>

          <template v-else>
            <p class="match-count">
              显示 {{ filtered.length }} 条，共 {{ memoryTotal }} 条
            </p>
            <div class="memory-list">
              <article v-for="item in filtered" :key="item.memory_id">
                <template v-if="memoryEditing === item.memory_id">
                  <textarea
                    v-model="memoryDraft"
                    maxlength="2000"
                    rows="4"
                    aria-label="更正记忆内容"
                    :disabled="memorySaving"
                  ></textarea>
                  <footer>
                    <button :disabled="memorySaving" @click="cancelEdit">
                      取消
                    </button>
                    <button
                      class="primary"
                      :disabled="
                        memorySaving || !chat?.session || !memoryDraft.trim()
                      "
                      @click="saveMemory(item)"
                    >
                      保存更正
                    </button>
                  </footer>
                </template>
                <template v-else>
                  <header>
                    <span>{{ selectedCharacter?.name || "她" }} 记得</span>
                    <div>
                      <time :datetime="item.updated_at">{{
                        displayTime(item.updated_at)
                      }}</time>
                      <button
                        class="memory-more"
                        :aria-expanded="openMenu === item.memory_id"
                        aria-label="更多操作"
                        :disabled="memorySaving"
                        @click="
                          openMenu =
                            openMenu === item.memory_id
                              ? undefined
                              : item.memory_id
                        "
                      >
                        <MoreHorizontal :size="17" />
                      </button>
                    </div>
                  </header>
                  <h3>{{ memoryTitle(item.content) }}</h3>
                  <p v-if="memoryDetail(item.content)">
                    {{ memoryDetail(item.content) }}
                  </p>
                  <footer v-if="openMenu === item.memory_id">
                    <button
                      v-if="item.source"
                      :disabled="memorySaving"
                      @click="
                        route(
                          'chat',
                          item.source.conversation_id,
                          item.source.turn_id,
                        )
                      "
                    >
                      查看来源
                    </button>
                    <span></span>
                    <button :disabled="memorySaving" @click="editMemory(item)">
                      <Pencil :size="14" />更正
                    </button>
                    <button
                      :disabled="memorySaving"
                      @click="memoryDelete = item"
                    >
                      <Trash2 :size="14" />删除
                    </button>
                  </footer>
                </template>
              </article>
            </div>
            <button
              v-if="memories.length < memoryTotal"
              class="load-more"
              :disabled="memoryLoading"
              @click="loadMore"
            >
              {{ memoryLoading ? "正在读取…" : "加载更多记忆" }}
            </button>
          </template>
        </template>
      </template>
    </div>
  </section>
</template>

<style scoped>
.memory-collection {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  flex: 1;
  width: 100%;
  max-width: 1060px;
  margin-inline: auto;
  overflow: hidden;
}
.collection-scroll {
  min-height: 0;
  flex: 1;
  width: 100%;
  box-sizing: border-box;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 4px 4px 8px;
  overscroll-behavior: contain;
}
.collection-scroll > .empty {
  min-height: 170px;
  max-width: 360px;
  margin: 24px auto;
  padding: 18px;
  gap: 9px;
  border: 0;
  border-radius: 0;
  background: transparent;
}
.collection-scroll > .empty h2 {
  font-size: 18px;
}
.collection-scroll > .empty p {
  font-size: 12px;
  line-height: 1.7;
}
.collection-intro {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  margin-bottom: 6px;
}
.collection-intro p {
  margin: 0;
  color: var(--muted);
  font-size: 11px;
}
.collection-toolbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.collection-switch {
  display: flex;
  flex-shrink: 0;
  gap: 4px;
  padding: 3px;
  border: 1px solid var(--soft);
  border-radius: 99px;
  background: #ffffff8c;
}
.collection-switch button {
  padding: 7px 12px;
  border-radius: 99px;
  color: var(--muted);
}
.collection-switch button.active {
  background: white;
  color: var(--accent);
  box-shadow: 0 2px 8px #0000000a;
}
.collection-filters {
  flex-shrink: 0;
  display: flex;
  flex: 0 1 auto;
  min-width: 0;
  gap: 10px;
}
.collection-filters select,
.memory-search {
  min-width: 0;
  height: 38px;
  box-sizing: border-box;
  padding: 8px 12px;
  border: 1px solid var(--soft);
  border-radius: 99px;
  background: #ffffffa8;
  color: var(--text);
}
.memory-search {
  display: block;
  flex: 1 1 220px;
  max-width: 380px;
}
.add-memory {
  flex-shrink: 0;
}
.memory-search input {
  box-sizing: border-box;
  width: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--text);
}
.memory-form {
  margin: 0 0 20px;
  padding: 20px;
  border: 1px solid var(--soft);
  border-radius: 18px;
  background: #ffffff9c;
}
.memory-form label {
  display: block;
  margin-bottom: 10px;
  font-weight: 700;
}
.memory-form textarea,
.memory-list textarea {
  box-sizing: border-box;
  width: 100%;
  padding: 13px;
  border: 1px solid var(--soft);
  border-radius: 12px;
  resize: vertical;
}
.memory-form footer,
.memory-list footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 12px;
}
.memory-error {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  margin: 12px 0;
  padding: 12px 16px;
  border-radius: 12px;
  background: color-mix(in srgb, var(--soft) 55%, white);
  color: var(--accent);
}
.match-count {
  margin: 0 0 10px;
  color: var(--muted);
  font-size: 11px;
}
.memory-list {
  display: grid;
  width: 100%;
  max-width: none;
  margin: 0;
  grid-template-columns: 1fr;
  gap: 0;
}
.memory-list article {
  box-sizing: border-box;
  min-width: 0;
  margin: 0;
  padding: 17px 14px;
  border: 0;
  border-bottom: 1px solid color-mix(in srgb, var(--soft) 58%, transparent);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  transition: background 0.2s ease;
}
.memory-list article:hover {
  background: color-mix(in srgb, var(--soft) 30%, transparent);
}
.memory-list article > header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--accent);
  font-size: 11px;
}
.memory-form input[type="datetime-local"] {
  box-sizing: border-box;
  width: 100%;
  margin-bottom: 8px;
  padding: 11px 13px;
  border: 1px solid var(--soft);
  border-radius: 12px;
  background: #fff;
}
.due-reminder {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin: 4px 0 14px;
  padding: 14px 16px;
  border: 1px solid color-mix(in srgb, var(--accent) 28%, var(--soft));
  border-radius: 15px;
  background: color-mix(in srgb, var(--soft) 42%, white);
}
.due-reminder p {
  margin: 4px 0 0;
  color: var(--text);
}
.add-matter {
  margin: 4px 0 10px auto;
}
.matter-list time {
  color: var(--muted);
}
.memory-list article > header > div {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--muted);
}
.memory-more {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  padding: 0;
  border-radius: 50%;
  color: var(--muted);
}
.memory-more:hover {
  background: color-mix(in srgb, var(--soft) 56%, white);
  color: var(--accent);
}
.memory-list h3 {
  margin: 8px 0 5px;
  color: var(--text);
  font-size: 15px;
}
.memory-list article > p {
  margin: 0;
  color: color-mix(in srgb, var(--text) 64%, var(--muted));
  font-size: 12px;
  line-height: 1.8;
  white-space: pre-wrap;
}
.memory-list footer > span {
  flex: 1;
}
.memory-list footer button {
  gap: 4px;
  color: var(--muted);
  font-size: 11px;
}
.memory-list footer {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid color-mix(in srgb, var(--soft) 55%, transparent);
}
.load-more {
  display: flex;
  margin: 20px auto 0;
  padding: 10px 20px;
  border: 1px solid var(--soft);
  border-radius: 99px;
  color: var(--accent);
}
@media (max-width: 900px) {
  .collection-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
  .collection-filters {
    flex-wrap: wrap;
  }
  .memory-search {
    max-width: none;
  }
  .memory-list {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 600px) {
  .collection-intro {
    align-items: flex-start;
    flex-direction: column;
  }
  .collection-filters {
    flex-direction: column;
  }
}
</style>
