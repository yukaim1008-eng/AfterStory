<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { LoaderCircle, Pencil, Plus, Sparkles, Trash2 } from "lucide-vue-next";
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
  store,
  route,
  beginMemory,
  cancelMemoryForm,
  createMemory,
  editMemory,
  saveMemory,
  confirmDeleteMemory,
  loadMemories,
} = useAfterStory();

const query = ref("");
const timeFilter = ref("all");
const typeFilter = ref("all");

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
      typeFilter.value === "all" ||
      (typeFilter.value === "manual" ? !item.source : !!item.source);
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
});
</script>

<template>
  <section class="memory-collection" aria-label="她记得的事">
    <header class="collection-intro">
      <p>只保存你主动选择的内容，随时可以更正或删除。</p>
      <button
        v-if="capabilities.memory"
        class="primary"
        :disabled="memorySaving || !chat?.session"
        @click="beginMemory()"
      >
        <Plus :size="16" />添加一条
      </button>
    </header>

    <div class="collection-filters">
      <select :value="selected" aria-label="筛选角色" @change="switchCharacter">
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
        <option value="manual">手动添加</option>
        <option value="source">来自聊天</option>
      </select>
      <input
        v-model="query"
        type="search"
        aria-label="搜索回忆"
        placeholder="搜索回忆…"
      />
    </div>

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
        <small v-if="memorySource">这段内容来自你选择的一条聊天消息。</small>
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
            :disabled="memorySaving || !chat?.session || !memoryDraft.trim()"
          >
            {{ memorySaving ? "保存中…" : "保存" }}
          </button>
        </footer>
      </form>

      <div v-if="memoryError" class="memory-error" role="alert">
        {{ memoryError }}
        <button
          :disabled="memoryLoading"
          @click="memories.length < memoryTotal ? loadMore() : loadMemories()"
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
        <h2>还没有保存的记忆</h2>
        <p>你可以手动添加，也可以从一条已完成的聊天消息中保存。</p>
        <button
          class="primary"
          :disabled="memorySaving || !chat?.session"
          @click="beginMemory()"
        >
          添加第一条
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
                <span>{{
                  item.kind === "fact" ? "你确认的事实" : "待确认的理解"
                }}</span>
                <time :datetime="item.updated_at">{{
                  displayTime(item.updated_at)
                }}</time>
              </header>
              <h3>她记得 · {{ excerpt(item.content, 24) }}</h3>
              <p>{{ item.content }}</p>
              <footer>
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
                <button :disabled="memorySaving" @click="memoryDelete = item">
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
  </section>
</template>

<style scoped>
.memory-collection {
  min-width: 0;
}
.collection-intro {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 16px;
}
.collection-intro p {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}
.collection-filters {
  display: grid;
  grid-template-columns: repeat(3, minmax(120px, auto)) minmax(180px, 1fr);
  gap: 10px;
  margin-bottom: 20px;
}
.collection-filters select,
.collection-filters input {
  min-width: 0;
  padding: 10px 13px;
  border: 1px solid var(--soft);
  border-radius: 99px;
  background: #ffffffa8;
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
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.memory-list article {
  box-sizing: border-box;
  min-width: 0;
  margin: 0;
  padding: 18px;
  border: 1px solid #ffffffcf;
  border-radius: 18px;
  background: #ffffffa8;
  box-shadow: 0 8px 28px #36232d09;
}
.memory-list article > header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--accent);
  font-size: 10px;
}
.memory-list h3 {
  margin: 14px 0 8px;
  color: var(--text);
  font-size: 14px;
}
.memory-list article > p {
  margin: 0;
  color: var(--muted);
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
.load-more {
  display: flex;
  margin: 20px auto 0;
  padding: 10px 20px;
  border: 1px solid var(--soft);
  border-radius: 99px;
  color: var(--accent);
}
@media (max-width: 900px) {
  .collection-filters {
    grid-template-columns: 1fr 1fr;
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
    grid-template-columns: 1fr;
  }
}
</style>
