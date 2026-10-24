<script setup lang="ts">
import {
  computed,
  nextTick,
  onMounted,
  onUnmounted,
  ref,
  type CSSProperties,
} from "vue";
import { BookOpen } from "lucide-vue-next";
import { useAfterStory } from "../composables/useAfterStory";
import CharacterAvatar from "../components/CharacterAvatar.vue";
import ChatCharacterScene from "../components/ChatCharacterScene.vue";
import {
  formatSceneDecorationText,
  resolveSceneDecorations,
} from "../sceneDecorations";
import type { SceneDecorationNote } from "../types";
import ChatConversation from "./ChatConversation.vue";
import MobileChatView from "./MobileChatView.vue";

const { character, chat, cover, connected, route, scrollArea } =
  useAfterStory();
const mobileQuery = window.matchMedia(
  "(max-width: 760px), (pointer: coarse) and (max-height: 500px) and (max-width: 1023px)",
);
const mobile = ref(mobileQuery.matches);
function switchLayout(event: MediaQueryListEvent) {
  const current = scrollArea.value;
  const nearBottom =
    !!current &&
    current.scrollHeight - current.clientHeight - current.scrollTop <= 56;
  const readingTop = current?.scrollTop || 0;
  mobile.value = event.matches;
  void nextTick().then(() =>
    requestAnimationFrame(() => {
      const next = scrollArea.value;
      if (next) next.scrollTop = nearBottom ? next.scrollHeight : readingTop;
    }),
  );
}
onMounted(() => mobileQuery.addEventListener("change", switchLayout));
onUnmounted(() => mobileQuery.removeEventListener("change", switchLayout));

const presence = computed(() => {
  if (!connected.value) return "稍等片刻";
  if (chat.value?.sending) return "正在想怎么和你说…";
  if (chat.value?.loading) return "正在翻开我们的对话…";
  return "在这里";
});
const decorations = computed(() =>
  character.value ? resolveSceneDecorations(character.value) : undefined,
);
function decorationText(text: string) {
  return character.value
    ? formatSceneDecorationText(text, character.value)
    : text;
}
function noteStyle(note?: SceneDecorationNote): CSSProperties | undefined {
  if (!note) return undefined;
  return {
    ...note.position,
    maxWidth: note.maxWidth,
    opacity: note.opacity,
    color: note.color,
    transform: `rotate(${note.rotate || 0}deg)`,
    fontFamily: note.fontStyle === "ui" ? undefined : "var(--font-character)",
  };
}
</script>

<template>
  <MobileChatView v-if="mobile" />
  <main
    v-else-if="character"
    id="main-content"
    tabindex="-1"
    class="chat-workspace"
    :data-version="chat?.session?.version_id"
  >
    <ChatCharacterScene />
    <section class="chat-glass">
      <p
        v-if="decorations?.topNote"
        :key="`${character.id}-top-note`"
        class="atmosphere-copy atmosphere-copy-top"
        :style="noteStyle(decorations.topNote)"
        aria-hidden="true"
      >
        {{ decorationText(decorations.topNote.text) }}
      </p>
      <p
        v-if="decorations?.bottomNote"
        :key="`${character.id}-bottom-note`"
        class="atmosphere-copy atmosphere-copy-bottom"
        :style="noteStyle(decorations.bottomNote)"
        aria-hidden="true"
      >
        {{ decorationText(decorations.bottomNote.text) }}
      </p>
      <header class="chat-header">
        <CharacterAvatar :character="character" :cover="cover(character)" />
        <div class="chat-identity">
          <h2>{{ character.name }}</h2>
          <div class="presence-line">
            <span class="presence-status"
              ><i :class="{ online: connected }"></i>{{ presence }}</span
            >
            <small
              v-if="decorations?.avatarNote"
              :key="`${character.id}-avatar-note`"
              class="avatar-note"
              :style="{
                opacity: decorations.avatarNote.opacity,
                color: decorations.avatarNote.color,
              }"
            >
              {{ decorationText(decorations.avatarNote.text) }}
            </small>
          </div>
        </div>
        <nav aria-label="当前角色快捷入口">
          <button aria-label="查看角色回忆" @click="route('history')">
            回忆
          </button>
          <button aria-label="角色资料" @click="route('profile')">
            角色资料<BookOpen :size="15" />
          </button>
        </nav>
      </header>
      <ChatConversation :character="character" :mobile="false" />
    </section>
  </main>
</template>

<style scoped>
.chat-workspace {
  position: absolute;
  inset: 0;
  width: auto;
  max-width: none;
  height: 100%;
  min-height: 0;
  margin: 0;
  overflow: hidden;
  border: 0;
  border-radius: 0;
  background: var(--background);
  box-shadow: none;
}

.chat-glass {
  position: absolute;
  top: calc(var(--chat-header-height) + clamp(10px, 1.5vh, 16px));
  right: var(--space-page);
  bottom: clamp(26px, 5vh, 52px);
  width: clamp(520px, 50vw, 880px);
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: clamp(20px, 2vw, 30px);
}

.chat-glass::before {
  position: absolute;
  inset: 0;
  z-index: 4;
  border: 1px solid #ffffffa8;
  border-radius: clamp(20px, 2vw, 30px);
  background:
    radial-gradient(
      ellipse at 54% 44%,
      rgba(255, 255, 255, 0.23) 0%,
      rgba(255, 255, 255, 0.1) 44%,
      transparent 72%
    ),
    linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.42) 0%,
      color-mix(in srgb, var(--glass-surface) 44%, transparent) 46%,
      rgba(255, 255, 255, 0.22) 100%
    );
  box-shadow:
    0 20px 58px color-mix(in srgb, var(--text) 9%, transparent),
    inset 0 1px rgba(255, 255, 255, 0.58);
  backdrop-filter: blur(8px) saturate(1.08);
  -webkit-backdrop-filter: blur(8px) saturate(1.08);
  content: "";
  pointer-events: none;
}

.chat-glass::after {
  position: absolute;
  inset: 1px;
  z-index: 5;
  border-radius: inherit;
  background: linear-gradient(
    105deg,
    rgba(255, 255, 255, 0.08),
    rgba(255, 255, 255, 0.17) 48%,
    transparent 78%
  );
  content: "";
  pointer-events: none;
}

.chat-header {
  position: relative;
  z-index: 7;
}

.atmosphere-copy {
  position: absolute;
  z-index: 6;
  max-width: 230px;
  margin: 0;
  color: color-mix(in srgb, var(--accent) 48%, transparent);
  font-size: clamp(15px, 1.08vw, 18px);
  font-weight: 400;
  line-height: 1.72;
  letter-spacing: 0.09em;
  text-align: right;
  text-shadow: 0 1px 5px rgba(255, 255, 255, 0.34);
  transform-origin: center;
  white-space: pre-line;
  pointer-events: none;
  animation: decoration-copy-enter 220ms ease-out both;
}

.atmosphere-copy-top {
  text-align: left;
}

.atmosphere-copy-bottom {
  color: color-mix(in srgb, var(--accent) 42%, transparent);
  font-size: clamp(14px, 0.96vw, 16px);
}

.chat-header {
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 11px;
  min-height: 78px;
  margin: 0 clamp(22px, 3vw, 38px);
  border-bottom: 1px solid #ffffff8f;
}

.chat-header .character-avatar {
  width: 42px;
  height: 42px;
  box-shadow: 0 8px 24px color-mix(in srgb, var(--accent) 16%, transparent);
}

.chat-header h2 {
  margin: 0 0 3px;
  font-size: 16px;
  font-weight: 620;
  line-height: 1.25;
  letter-spacing: 0.07em;
}

.presence-status {
  color: color-mix(in srgb, var(--muted) 82%, transparent);
  font-size: var(--type-caption-size);
  letter-spacing: 0.04em;
}

.presence-line {
  display: flex;
  align-items: baseline;
  gap: 9px;
  min-width: 0;
}

.avatar-note {
  color: color-mix(in srgb, var(--accent) 64%, var(--muted));
  font-size: 11px;
  font-weight: 420;
  line-height: 1.4;
  letter-spacing: 0.045em;
  white-space: nowrap;
  animation: decoration-copy-enter 180ms ease-out both;
}

.avatar-note::before {
  margin-right: 8px;
  color: color-mix(in srgb, var(--accent) 36%, transparent);
  content: "／";
}

@keyframes decoration-copy-enter {
  from {
    filter: opacity(0);
    translate: 0 3px;
  }
  to {
    filter: opacity(1);
    translate: 0 0;
  }
}

.chat-header i {
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-right: 6px;
  border-radius: 50%;
  background: #baaeb5;
}

.chat-header i.online {
  background: #76a98b;
  box-shadow: 0 0 0 3px #76a98b1c;
}

.chat-header nav {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.chat-header nav button {
  gap: 5px;
  padding: 7px 10px;
  border-radius: 99px;
  color: color-mix(in srgb, var(--text) 62%, transparent);
  font-size: var(--type-caption-size);
  letter-spacing: 0.03em;
}

.chat-header nav button:hover {
  background: #ffffff52;
  color: var(--accent);
}

@media (max-width: 900px) {
  .chat-glass {
    right: 18px;
    width: min(64%, 620px);
  }
  .chat-header {
    margin-inline: 22px;
  }
  .avatar-note {
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}
@media (prefers-reduced-motion: reduce) {
  .atmosphere-copy,
  .avatar-note {
    animation: none;
  }
}
</style>
