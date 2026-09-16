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
import CharacterAvatar from "../components/CharacterAvatar.vue";
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
          <div class="settings-nav-list">
            <button
              v-for="item in sections"
              :key="item.id"
              :class="{ active: section === item.id }"
              @click="section = item.id"
            >
              <component :is="item.icon" :size="18" />{{ item.label }}
            </button>
          </div>
          <div class="settings-companion">
            <CharacterAvatar :character="character" :cover="cover(character)" />
            <div>
              <small>当前陪伴角色</small>
              <strong>{{ character.name }}</strong>
              <span>按你的习惯来吧。</span>
            </div>
          </div>
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
                <h2>外观</h2>
                <p>整理当前角色在这个浏览器中的主题与封面。</p>
              </div>
            </header>
            <section class="appearance-section">
              <header class="section-header">
                <h3>角色主题</h3>
                <p>页面色彩会随着当前角色轻轻变化。</p>
              </header>
              <div class="setting-row appearance-row">
                <div>
                  <strong>当前角色</strong>
                  <p>正在使用她的主题、背景与装饰。</p>
                </div>
                <div class="appearance-character-value">
                  <CharacterAvatar
                    :character="character"
                    :cover="cover(character)"
                  />
                  <strong>{{ character.name }}</strong>
                </div>
              </div>
              <div class="setting-row appearance-row">
                <div>
                  <strong>主题色</strong>
                  <p>当前角色的主题强调色。</p>
                </div>
                <div class="theme-color-value">
                  <span
                    class="theme-swatch"
                    :style="{ background: character.theme.accent }"
                    aria-hidden="true"
                  ></span>
                  <span
                    >{{ character.romanized }} ·
                    {{ character.theme.accent }}</span
                  >
                </div>
              </div>
            </section>
            <section class="appearance-section cover-section">
              <header class="section-header">
                <h3>角色封面</h3>
                <p>只影响当前角色在这个浏览器中的展示。</p>
              </header>
              <div class="cover-layout">
                <Portrait
                  :source="cover(character).source"
                  :crop="cover(character).crop.chat"
                  :name="character.name"
                />
                <div class="cover-controls">
                  <p class="cover-copy">
                    更换、调整或恢复默认封面，不会影响聊天记录和角色记忆。
                  </p>
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
                  <p class="fine-print">
                    封面和裁切按当前用户、当前角色分别保存。
                  </p>
                </div>
              </div>
            </section>
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
  display: block;
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
  background: color-mix(in srgb, var(--surface) 92%, transparent);
  box-shadow: 0 14px 40px #36232d0a;
}
.settings-content {
  min-width: 0;
  min-height: 0;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 16px 28px 22px;
  background: linear-gradient(
    145deg,
    color-mix(in srgb, var(--soft) 20%, transparent),
    #ffffff72 46%
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
  margin: 0 0 7px -10px;
  padding: 6px 10px;
  color: var(--muted);
  font-size: 11px;
}
.settings-hero h1 {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 5px 0 5px;
  color: var(--text);
  font-size: clamp(30px, 2.2vw, 38px);
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
  grid-template-columns: 200px minmax(0, 1fr);
  flex: 1;
  min-height: 0;
  overflow: hidden;
  gap: 32px;
  margin-top: 14px;
}
.settings-nav {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 8px 18px 14px 0;
  border-right: 1px solid color-mix(in srgb, var(--soft) 55%, transparent);
}
.settings-nav-list {
  display: grid;
  gap: 4px;
}
.settings-nav button {
  position: relative;
  justify-content: flex-start;
  gap: 10px;
  padding: 11px 12px;
  border-radius: 10px;
  color: var(--muted);
  font-size: 13px;
}
.settings-nav button.active {
  background: color-mix(in srgb, var(--soft) 48%, white);
  color: var(--accent) !important;
}
.settings-nav button.active::before {
  position: absolute;
  left: -1px;
  width: 3px;
  height: 18px;
  border-radius: 99px;
  background: var(--accent);
  content: "";
}
.settings-companion {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: auto;
  padding-top: 18px;
  color: var(--muted);
}
.settings-companion .character-avatar {
  width: 36px;
  height: 36px;
}
.settings-companion > div {
  display: grid;
  gap: 1px;
}
.settings-companion small {
  font-size: 9px;
  letter-spacing: 1px;
}
.settings-companion strong {
  color: var(--text);
  font-size: 12px;
}
.settings-companion span {
  font-family: "Kaiti SC", "STKaiti", "KaiTi", serif;
  font-size: 11px;
}
.settings-panel {
  min-width: 0;
  min-height: 0;
  width: min(100%, 1060px);
  height: 100%;
  box-sizing: border-box;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: clamp(20px, 2.4vw, 32px);
  align-self: stretch;
  max-height: 100%;
  border: 1px solid #ffffffc7;
  border-radius: 18px;
  background: #ffffff7a;
  box-shadow: none;
}
.panel-title {
  display: flex;
  align-items: flex-start;
  gap: 13px;
  padding-bottom: 14px;
  border-bottom: 1px solid color-mix(in srgb, var(--soft) 72%, transparent);
}
.panel-title > svg {
  margin-top: 2px;
  color: var(--accent);
}
.panel-title h2 {
  margin: 0 0 5px;
  color: var(--text);
  font-size: 20px;
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
  min-height: 66px;
  padding: 13px 0;
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
.appearance-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
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
.appearance-section {
  padding: 22px 0;
  border-bottom: 1px solid color-mix(in srgb, var(--soft) 72%, transparent);
}
.section-header {
  display: block;
  padding-bottom: 8px;
}
.section-header h3 {
  margin: 0 0 5px;
  color: var(--text);
  font-size: 16px;
}
.section-header p {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.7;
}
.appearance-row {
  min-height: 70px;
}
.appearance-character-value,
.theme-color-value {
  display: flex;
  align-items: center;
  gap: 9px;
  flex-shrink: 0;
  color: var(--text);
  font-size: 13px;
}
.appearance-character-value .character-avatar {
  width: 34px;
  height: 34px;
}
.theme-swatch {
  width: 24px;
  height: 24px;
  border: 3px solid #ffffffb8;
  border-radius: 50%;
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 30%, transparent);
}
.cover-layout {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr);
  gap: clamp(24px, 4vw, 56px);
  align-items: start;
  padding-top: 16px;
}
.cover-layout > .portrait {
  width: 100%;
  aspect-ratio: 2 / 3;
  border: 1px solid #ffffffc7;
  border-radius: 14px;
  box-shadow: none;
}
.cover-controls {
  padding-top: 4px;
}
.cover-copy {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.8;
}
.cover-controls .fine-print {
  margin-top: 16px;
}
.voice-note {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 16px;
  padding: 15px 0;
  border-bottom: 1px solid color-mix(in srgb, var(--soft) 72%, transparent);
  border-radius: 0;
  background: transparent;
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
  padding: 16px 0;
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
  .settings-layout {
    grid-template-columns: 170px minmax(0, 1fr);
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
    border-right: 0;
    padding: 0;
  }
  .settings-nav-list {
    grid-template-columns: 1fr 1fr;
  }
  .settings-companion {
    display: none;
  }
  .cover-layout {
    grid-template-columns: minmax(210px, 280px) minmax(0, 1fr);
    gap: 22px;
  }
}
</style>
