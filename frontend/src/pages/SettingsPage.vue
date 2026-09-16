<script setup lang="ts">
import {
  ArrowLeft,
  Database,
  ImagePlus,
  Monitor,
  Palette,
  RotateCcw,
  Send,
  Settings2,
  SlidersHorizontal,
  Sparkles,
  Volume2,
} from "lucide-vue-next";
import { useAfterStory } from "../composables/useAfterStory";
import CharacterSidebar from "../components/CharacterSidebar.vue";
import Portrait from "../Portrait.vue";

const {
  character,
  cover,
  connected,
  editing,
  preferences,
  resetConfirm,
  route,
  section,
} = useAfterStory();

const sections = [
  { id: "general", label: "通用", icon: Settings2 },
  { id: "appearance", label: "外观", icon: Palette },
  { id: "voice", label: "声音", icon: Volume2 },
  { id: "data", label: "数据管理", icon: Database },
] as const;
</script>

<template>
  <main
    v-if="character"
    id="main-content"
    tabindex="-1"
    class="workspace settings-workspace"
  >
    <CharacterSidebar compact />
    <section class="settings-content">
      <header class="settings-hero">
        <button class="back-to-chat" @click="route('chat')">
          <ArrowLeft :size="15" />返回聊天
        </button>
        <span>SETTINGS</span>
        <h1>按你的习惯来 <Sparkles :size="31" /></h1>
        <p>让每一次相见，都更合你的心意。</p>
      </header>

      <div class="settings-layout">
        <nav class="settings-nav" aria-label="设置类别">
          <button
            v-for="item in sections"
            :key="item.id"
            :class="{ active: section === item.id }"
            @click="section = item.id"
          >
            <component :is="item.icon" :size="18" />{{ item.label }}
          </button>
        </nav>

        <div class="settings-panel">
          <template v-if="section === 'general'">
            <header class="panel-title">
              <SlidersHorizontal :size="23" />
              <div>
                <h2>阅读与交流</h2>
                <p>调整你和她说话的方式。</p>
              </div>
            </header>
            <div class="setting-row">
              <div>
                <strong>聊天字体大小</strong>
                <p>找到适合长时间阅读的大小。</p>
              </div>
              <div class="segmented" role="group" aria-label="聊天字体大小">
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
              <label class="select-control"
                ><Send :size="16" /><select
                  v-model="preferences.send"
                  aria-label="发送方式"
                >
                  <option value="enter">Enter 发送</option>
                  <option value="ctrl">Ctrl / ⌘ + Enter</option>
                </select></label
              >
            </div>
            <div class="setting-row">
              <div>
                <strong>界面动效</strong>
                <p>角色、页面与控件的轻柔过渡。</p>
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
              </button>
            </div>
          </template>

          <template v-if="section === 'appearance'">
            <header class="panel-title">
              <Palette :size="23" />
              <div>
                <h2>角色主题与封面</h2>
                <p>当前角色的主题和封面只保存在这个浏览器。</p>
              </div>
            </header>
            <div class="appearance-card">
              <Portrait
                :source="cover(character).source"
                :crop="cover(character).crop.chat"
                :name="character.name"
              />
              <div>
                <span class="pill">当前使用中</span>
                <h3>{{ character.name }}</h3>
                <p>页面的主题色、背景和装饰会随她一起变化。</p>
                <div class="appearance-actions">
                  <button
                    class="primary"
                    :disabled="!connected"
                    @click="editing = true"
                  >
                    <ImagePlus :size="16" />更换封面
                  </button>
                  <button :disabled="!connected" @click="editing = true">
                    调整位置
                  </button>
                  <button :disabled="!connected" @click="resetConfirm = true">
                    <RotateCcw :size="15" />恢复默认
                  </button>
                </div>
              </div>
            </div>
            <p class="fine-print">
              封面和裁切按当前用户、当前角色分别保存；聊天记录与角色记忆不会被修改。
            </p>
          </template>

          <template v-if="section === 'voice'">
            <header class="panel-title">
              <Volume2 :size="23" />
              <div>
                <h2>声音</h2>
                <p>声音资料和服务接入后，会使用这里的偏好。</p>
              </div>
            </header>
            <div class="voice-note">
              <Volume2 :size="26" />
              <div>
                <strong>语音尚未启用</strong>
                <p>现在仍可正常文字交流。不会模拟语音已经可用。</p>
              </div>
            </div>
            <div class="setting-row">
              <div>
                <strong>语音播放方式</strong>
                <p>提前保存偏好，接入后生效。</p>
              </div>
              <select v-model="preferences.voice" aria-label="语音播放方式">
                <option value="manual">手动播放</option>
                <option value="auto">自动播放</option>
              </select>
            </div>
          </template>

          <template v-if="section === 'data'">
            <header class="panel-title">
              <Database :size="23" />
              <div>
                <h2>数据管理</h2>
                <p>查看留在你们之间的记录。</p>
              </div>
            </header>
            <button
              class="data-link"
              aria-label="个人记忆"
              @click="route('memory')"
            >
              <span class="data-icon"><Sparkles :size="21" /></span>
              <div>
                <strong>角色记忆</strong>
                <p>查看、更正或删除你主动保存的信息。</p>
              </div>
              <span>→</span>
            </button>
            <button class="data-link" @click="route('history')">
              <span class="data-icon"><Monitor :size="21" /></span>
              <div>
                <strong>聊天记录</strong>
                <p>回到每一段真实保存的相见。</p>
              </div>
              <span>→</span>
            </button>
            <p class="fine-print">
              当前为本地开发身份，暂不提供账号登录与跨设备同步。
            </p>
          </template>
        </div>
      </div>
    </section>
  </main>
</template>

<style scoped>
.workspace.settings-workspace {
  display: grid;
  grid-template-columns: 230px minmax(0, 1fr);
  width: 100%;
  max-width: 1800px;
  height: calc(
    100dvh - var(--desktop-header-height) - 2 * var(--page-padding-y)
  );
  min-height: 0;
  margin: var(--page-padding-y) auto;
  overflow: hidden;
  border: 1px solid #ffffffba;
  border-radius: var(--radius-panel);
  background: color-mix(in srgb, var(--surface) 88%, transparent);
  box-shadow: var(--shadow-panel);
}
.settings-content {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 20px 24px;
  background: linear-gradient(
    145deg,
    color-mix(in srgb, var(--soft) 38%, transparent),
    #ffffff88 46%
  );
}
.settings-hero > span {
  color: var(--muted);
  font-size: 10px;
  letter-spacing: 5px;
}
.settings-hero {
  flex-shrink: 0;
}
.back-to-chat {
  margin: -8px 0 13px -10px;
  padding: 6px 10px;
  color: var(--muted);
  font-size: 11px;
}
.settings-hero h1 {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 10px 0 8px;
  color: var(--text);
  font-size: clamp(32px, 2.6vw, 42px);
}
.settings-hero h1 svg {
  color: var(--accent);
  transform: rotate(-12deg);
}
.settings-hero p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}
.settings-layout {
  display: grid;
  grid-template-columns: 160px minmax(0, 720px);
  flex: 1;
  min-height: 0;
  overflow: hidden;
  gap: 24px;
  margin-top: 20px;
}
.settings-nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-self: start;
  padding: 8px;
  border: 1px solid #ffffffd8;
  border-radius: 18px;
  background: #ffffff8a;
}
.settings-nav button {
  justify-content: flex-start;
  padding: 12px;
  border-radius: 12px;
  color: var(--muted);
  font-size: 13px;
}
.settings-nav button.active {
  background: color-mix(in srgb, var(--soft) 74%, white);
  color: var(--accent) !important;
}
.settings-panel {
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 20px;
  align-self: start;
  max-height: 100%;
  border: 1px solid #ffffffd7;
  border-radius: 22px;
  background: #ffffff8f;
  box-shadow: 0 12px 42px #36232d08;
}
.panel-title {
  display: flex;
  align-items: flex-start;
  gap: 13px;
  padding-bottom: 16px;
  border-bottom: 1px solid color-mix(in srgb, var(--soft) 72%, transparent);
}
.panel-title > svg {
  margin-top: 2px;
  color: var(--accent);
}
.panel-title h2 {
  margin: 0 0 5px;
  color: var(--text);
  font-size: 19px;
}
.panel-title p,
.setting-row p {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.75;
}
.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 22px;
  min-height: 76px;
  padding: 14px 0;
  border-bottom: 1px solid color-mix(in srgb, var(--soft) 72%, transparent);
}
.setting-row strong,
.data-link strong,
.voice-note strong {
  display: block;
  color: var(--text);
  font-size: 14px;
}
.segmented {
  flex-shrink: 0;
  padding: 3px;
  border: 1px solid var(--soft);
  border-radius: 12px;
  background: #ffffffa8;
}
.segmented button {
  min-width: 46px;
  padding: 7px 10px;
  font-size: 12px;
}
.segmented button.active {
  border-radius: 8px;
  background: var(--soft);
  color: var(--accent) !important;
}
.select-control {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--accent);
}
.select-control select,
.setting-row select {
  max-width: 180px;
  padding: 9px 12px;
  border: 1px solid var(--soft);
  border-radius: 10px;
  background: #ffffffa8;
  color: var(--text);
  font-size: 12px;
}
.appearance-card {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  gap: 25px;
  align-items: center;
  padding: 20px 0;
}
.appearance-card > .portrait {
  height: 180px;
  border-radius: 16px;
  box-shadow: 0 12px 28px #36232d20;
}
.appearance-card h3 {
  margin: 13px 0 8px;
  color: var(--text);
  font-size: 20px;
}
.appearance-card p {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.8;
}
.appearance-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 18px;
}
.appearance-actions button:not(.primary) {
  color: var(--muted);
  font-size: 12px;
}
.fine-print {
  margin: 0;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.8;
}
.voice-note {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 22px;
  padding: 20px;
  border-radius: 16px;
  background: color-mix(in srgb, var(--soft) 58%, white);
}
.voice-note > svg {
  color: var(--accent);
}
.voice-note p {
  margin: 5px 0 0;
  color: var(--muted);
  font-size: 12px;
}
.data-link {
  display: grid;
  grid-template-columns: 46px minmax(0, 1fr) auto;
  width: 100%;
  gap: 14px;
  align-items: center;
  padding: 19px 0;
  border-bottom: 1px solid color-mix(in srgb, var(--soft) 72%, transparent);
  text-align: left;
}
.data-link p {
  margin: 5px 0 0;
  color: var(--muted);
  font-size: 12px;
}
.data-link > span:last-child {
  color: var(--accent);
  font-size: 22px;
}
.data-icon {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 50%;
  background: var(--soft);
  color: var(--accent);
}
.data-link + .fine-print {
  margin-top: 22px;
}
@media (max-width: 900px) {
  .workspace.settings-workspace {
    grid-template-columns: 190px minmax(0, 1fr);
  }
  .settings-layout {
    grid-template-columns: 130px minmax(0, 1fr);
    gap: 20px;
  }
  .setting-row {
    align-items: flex-start;
    flex-direction: column;
  }
}
@media (max-width: 700px) {
  .workspace.settings-workspace {
    grid-template-columns: 1fr;
    height: calc(100dvh - 78px);
    min-height: 500px;
  }
  .settings-content {
    padding: 26px 18px;
  }
  .settings-layout {
    grid-template-columns: 1fr;
    margin-top: 25px;
  }
  .settings-nav {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
  .appearance-card {
    grid-template-columns: 110px minmax(0, 1fr);
    gap: 16px;
  }
  .appearance-card > .portrait {
    height: 176px;
  }
}
</style>
