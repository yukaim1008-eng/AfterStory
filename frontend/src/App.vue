<script setup lang="ts">
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
  Pencil,
  Plus,
  RotateCcw,
  Settings,
  Sparkles,
  Trash2,
  Volume2,
} from "lucide-vue-next";
import Portrait from "./Portrait.vue";
import CoverEditor from "./CoverEditor.vue";
import ChatPage from "./pages/ChatPage.vue";
import CharacterSidebar from "./components/CharacterSidebar.vue";
import CharactersPage from "./pages/CharactersPage.vue";
import HomePage from "./pages/HomePage.vue";
import MemoriesPage from "./pages/MemoriesPage.vue";
import SettingsPage from "./pages/SettingsPage.vue";
import AppShell from "./components/AppShell.vue";
import {
  createAfterStory,
  provideAfterStory,
} from "./composables/useAfterStory";
const state = createAfterStory();
provideAfterStory(state);
const {
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
} = state;
</script>

<template>
  <AppShell
    :character="character"
    :source="character ? cover(character).source : undefined"
    :page="page"
    :font="preferences.font"
    :motion="preferences.motion"
    @navigate="route"
  >
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
      <HomePage v-if="page === 'home'" />
      <CharactersPage v-else-if="page === 'characters'" />
      <ChatPage v-else-if="page === 'chat'" />
      <MemoriesPage v-else-if="page === 'history' || page === 'memory'" />
      <SettingsPage v-else-if="page === 'settings'" />
      <main
        v-else
        id="main-content"
        tabindex="-1"
        class="workspace"
        :class="{ 'secondary-workspace': page !== 'chat' }"
      >
        <CharacterSidebar compact />
        <section class="content-area">
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
              <p v-if="!legacyVersion">{{ character.description }}</p>
              <p v-else>
                这段历史会话继续使用创建时绑定的角色版本。当前封面与主题来自已安装的角色资料。
              </p>
              <p class="muted">
                当前资料用于验证交流流程，不代表完整正式角色设定。后续资料会以独立版本补全。
              </p>
            </section>
            <div class="metadata-row">
              <strong>剧情进度</strong
              ><span>{{
                chat?.session?.checkpoint || character.checkpointLabel
              }}</span
              ><button disabled title="剧情更新接口尚未实现">查看更新</button>
            </div>
            <div v-if="chat?.session" class="metadata-row">
              <strong>会话版本</strong
              ><span>{{ chat.session.version_id }}</span>
            </div>
            <div v-if="chat?.session" class="metadata-row">
              <strong>开始时间</strong
              ><time :datetime="chat.session.created_at || undefined">{{
                displayTime(chat.session.created_at)
              }}</time>
            </div></template
          >
          <template v-if="page === 'history'"
            ><small class="eyebrow">OUR CONVERSATIONS</small>
            <h1>聊过的那些事</h1>
            <p class="muted">从一句话，回到熟悉的交流。</p>
            <div class="filter-row">
              <button
                class="active"
                :disabled="historyLoading"
                @click="loadSessions()"
              >
                全部角色</button
              ><span>{{ historyTotal }} 段对话</span>
            </div>
            <div v-if="historyLoading && !sessions.length" class="empty">
              正在读取对话…
            </div>
            <div v-if="historyError" class="history-error" role="alert">
              {{ historyError
              }}<button
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
              <p>发送第一条消息后，再回来看看。</p>
            </div>
            <button
              v-for="item in sessions"
              :key="item.conversation_id"
              class="history-row"
              :disabled="!characters.some((c) => c.id === item.character_id)"
              @click="resume(item)"
            >
              <span class="history-initial">{{
                characters
                  .find((c) => c.id === item.character_id)
                  ?.name.slice(0, 1) || "旧"
              }}</span>
              <div>
                <strong>{{
                  characters.find((c) => c.id === item.character_id)?.name ||
                  item.name
                }}</strong>
                <p>{{ item.preview || "还没有消息" }}</p>
                <small
                  >{{ item.turns }} 轮对话 ·
                  <time :datetime="item.last_activity_at || undefined">{{
                    displayTime(item.last_activity_at)
                  }}</time></small
                >
                <small class="history-version"
                  >{{ item.version_id }} · {{ item.checkpoint }}</small
                >
              </div>
              <MessageCircle :size="17" />
            </button>
            <button
              v-if="historyOffset < historyTotal"
              class="load-older"
              :disabled="historyLoading"
              @click="loadSessions(true)"
            >
              {{ historyLoading ? "正在读取…" : "加载更多对话" }}
            </button>
          </template>
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
                      <p>查看、更正或删除你主动保存的信息。</p>
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
            ><div class="memory-heading">
              <div>
                <small class="eyebrow">WHAT SHE REMEMBERS</small>
                <h1>个人记忆</h1>
                <p class="muted">
                  只保存你主动选择的内容，并且随时可以更正或删除。
                </p>
              </div>
              <button
                v-if="capabilities.memory"
                class="primary"
                @click="beginMemory()"
              >
                <Plus :size="16" />添加一条
              </button>
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
                <small v-if="memorySource"
                  >这段内容来自你选择的一条聊天消息。</small
                >
                <footer>
                  <button type="button" @click="cancelMemoryForm">取消</button>
                  <button
                    class="primary"
                    :disabled="memorySaving || !memoryDraft.trim()"
                  >
                    {{ memorySaving ? "保存中…" : "保存" }}
                  </button>
                </footer>
              </form>
              <div v-if="memoryError" class="memory-error" role="alert">
                {{ memoryError }}
                <button @click="loadMemories()">刷新</button>
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
                <button class="primary" @click="beginMemory()">
                  添加第一条
                </button>
              </div>
              <div v-else class="memory-list">
                <article v-for="item in memories" :key="item.memory_id">
                  <template v-if="memoryEditing === item.memory_id">
                    <textarea
                      v-model="memoryDraft"
                      maxlength="2000"
                      rows="4"
                      aria-label="更正记忆内容"
                    ></textarea>
                    <footer>
                      <button
                        @click="
                          memoryEditing = undefined;
                          memoryDraft = '';
                        "
                      >
                        取消
                      </button>
                      <button
                        class="primary"
                        :disabled="memorySaving || !memoryDraft.trim()"
                        @click="saveMemory(item)"
                      >
                        保存更正
                      </button>
                    </footer>
                  </template>
                  <template v-else>
                    <header>
                      <span>你确认的事实</span>
                      <time :datetime="item.updated_at">{{
                        displayTime(item.updated_at)
                      }}</time>
                    </header>
                    <p>{{ item.content }}</p>
                    <footer>
                      <button
                        v-if="item.source"
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
                      <button @click="editMemory(item)">
                        <Pencil :size="14" />更正
                      </button>
                      <button @click="memoryDelete = item">
                        <Trash2 :size="14" />删除
                      </button>
                    </footer>
                  </template>
                </article>
                <small class="memory-count">共 {{ memoryTotal }} 条</small>
              </div>
            </template></template
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
      <div
        v-if="memoryDelete"
        class="modal-shade"
        @keydown.esc="memoryDelete = undefined"
      >
        <section
          class="modal small-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="memory-delete-title"
        >
          <h2 id="memory-delete-title">删除这条个人记忆？</h2>
          <p class="muted">
            她之后不会再把这条内容作为个人记忆使用。原始聊天记录仍会保留。
          </p>
          <footer>
            <button @click="memoryDelete = undefined">取消</button>
            <button
              class="primary"
              :disabled="memorySaving"
              @click="confirmDeleteMemory"
            >
              <Trash2 :size="16" />确认删除
            </button>
          </footer>
        </section>
      </div>
    </template>
  </AppShell>
</template>
