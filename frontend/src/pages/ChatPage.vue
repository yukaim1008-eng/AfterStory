<script setup lang="ts">
import { computed, type CSSProperties } from "vue";
import { ArrowUp, BookOpen, LoaderCircle, Plus } from "lucide-vue-next";
import { useAfterStory } from "../composables/useAfterStory";
import CharacterAvatar from "../components/CharacterAvatar.vue";
import ChatCharacterScene from "../components/ChatCharacterScene.vue";
import type { SceneDecorationNote } from "../types";

const {
  character,
  chat,
  cover,
  selected,
  connected,
  capabilities,
  targetTurn,
  scrollArea,
  preferences,
  displayTime,
  route,
  openChat,
  send,
  retryChat,
  inputKey,
  recoverDraft,
  loadOlder,
  beginMemory,
  saveChat,
} = useAfterStory();

const presence = computed(() => {
  if (!connected.value) return "稍等片刻";
  if (chat.value?.sending) return "正在想怎么和你说…";
  if (chat.value?.loading) return "正在翻开我们的对话…";
  return "在这里";
});
const decorations = computed(() => character.value?.sceneDecorations);

function noteStyle(note?: SceneDecorationNote): CSSProperties | undefined {
  if (!note) return undefined;
  return {
    ...note.position,
    maxWidth: note.maxWidth,
    opacity: note.opacity,
    color: note.color,
    transform: `rotate(${note.rotate || 0}deg)`,
    fontFamily:
      note.fontStyle === "ui"
        ? undefined
        : '"Kaiti SC", "STKaiti", "KaiTi", serif',
  };
}
</script>

<template>
  <main
    v-if="character"
    id="main-content"
    tabindex="-1"
    class="chat-workspace"
    :data-version="chat?.session?.version_id"
  >
    <ChatCharacterScene />

    <section class="chat-glass">
      <p
        v-if="decorations?.topNote"
        class="atmosphere-copy atmosphere-copy-top"
        :style="noteStyle(decorations.topNote)"
        aria-hidden="true"
      >
        {{ decorations.topNote.text }}
      </p>
      <p
        v-if="decorations?.bottomNote"
        class="atmosphere-copy atmosphere-copy-bottom"
        :style="noteStyle(decorations.bottomNote)"
        aria-hidden="true"
      >
        {{ decorations.bottomNote.text }}
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
              class="avatar-note"
              :style="{
                opacity: decorations.avatarNote.opacity,
                color: decorations.avatarNote.color,
              }"
              >{{ decorations.avatarNote.text }}</small
            >
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
          <span class="welcome-mark">✳</span>
          <small>ANOTHER DAY, ANOTHER STORY</small>
          <h2>故事之外，<br />还有话想对你说。</h2>
          <p>从今天的一件小事开始吧。</p>
        </div>
        <div
          v-for="turn in chat?.turns"
          :id="`turn-${turn.turn_id}`"
          :key="turn.turn_id"
          class="turn"
          :class="{ 'source-turn': targetTurn === turn.turn_id }"
          :data-turn-id="turn.turn_id"
        >
          <time class="turn-time" :datetime="turn.created_at || undefined">{{
            displayTime(turn.created_at)
          }}</time>
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
            <button
              v-if="
                message.role === 'user' &&
                turn.status === 'completed' &&
                capabilities.memory
              "
              class="remember-message"
              @click="beginMemory(message.text, message.message_id)"
            >
              <Plus :size="13" />记住这件事
            </button>
          </div>
          <div v-if="turn.status !== 'completed'" class="turn-status">
            {{
              turn.status === "processing"
                ? "回复处理中，可刷新确认结果"
                : "这次回复未完成"
            }}
            <button
              v-if="turn.status === 'failed' && turn.sequence === chat?.total"
              :disabled="chat?.sending"
              @click="
                send({
                  request_id: turn.request_id,
                  text: turn.messages.find((m) => m.role === 'user')!.text,
                })
              "
            >
              重试
            </button>
            <button
              v-else-if="turn.status === 'processing'"
              @click="openChat(selected)"
            >
              刷新
            </button>
          </div>
        </div>
        <button
          v-if="chat?.turns.length && chat.turns.at(-1)!.sequence < chat.total"
          class="load-older"
          :disabled="chat.loading"
          @click="route('chat')"
        >
          返回最新对话
        </button>
        <div
          v-if="
            chat?.pending &&
            !chat.turns.some(
              (turn) => turn.request_id === chat.pending?.request_id,
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
          {{ chat.error }}
          <button type="button" :disabled="chat.sending" @click="retryChat">
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
            :placeholder="`想和${character.name}说些什么……`"
            maxlength="8000"
            rows="2"
            :disabled="!connected"
            @input="saveChat(selected)"
            @keydown="inputKey"
          ></textarea>
          <textarea
            v-else
            aria-label="消息"
            :placeholder="`想和${character.name}说些什么……`"
            disabled
          ></textarea>
          <button
            class="send-button"
            :aria-label="character.sendControl.label"
            :disabled="
              !connected ||
              !chat?.id ||
              !chat?.session ||
              chat.sending ||
              chat.loading ||
              !chat.draft.trim() ||
              !!chat.pending
            "
          >
            <LoaderCircle v-if="chat?.sending" class="spin" :size="20" />
            <img
              v-else-if="character.sendControl.image"
              :src="character.sendControl.image"
              alt=""
            />
            <ArrowUp v-else :size="21" />
          </button>
        </div>
        <div class="composer-caption">
          <span>{{
            preferences.send === "enter"
              ? "Enter 发送 · Shift + Enter 换行"
              : "Ctrl / ⌘ + Enter 发送"
          }}</span>
          <span>聊天记录保存在本机</span>
        </div>
      </form>
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

.chat-header,
.messages,
.composer {
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
}

.avatar-note::before {
  margin-right: 8px;
  color: color-mix(in srgb, var(--accent) 36%, transparent);
  content: "／";
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

.messages {
  flex: 1;
  min-height: 0;
  overflow: auto;
  overscroll-behavior: contain;
  padding: 20px clamp(24px, 3vw, 40px) 14px;
  scrollbar-width: thin;
  scrollbar-color: var(--soft) transparent;
}

.message {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  margin: 0 0 18px;
}

.message.user {
  align-items: flex-end;
}

.message-author {
  margin: 0 6px;
  color: color-mix(in srgb, var(--muted) 82%, transparent);
  font-size: 9px;
  font-weight: 560;
  letter-spacing: 0.08em;
}

.bubble {
  max-width: min(76%, 560px);
  padding: 2px 4px 3px 13px;
  border: 0;
  border-left: 2px solid color-mix(in srgb, var(--accent) 44%, transparent);
  border-radius: 0 10px 10px 0;
  background: linear-gradient(90deg, #ffffff3d, #ffffff08);
  box-shadow: none;
  color: var(--text);
  font-size: var(--type-body-size);
  font-weight: 420;
  line-height: 1.78;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.message.user .bubble {
  max-width: min(70%, 500px);
  padding: 9px 13px;
  border: 1px solid color-mix(in srgb, var(--accent) 14%, transparent);
  border-radius: 17px 5px 17px 17px;
  background: color-mix(in srgb, var(--soft) 58%, #ffffff82);
  box-shadow: 0 5px 16px color-mix(in srgb, var(--accent) 6%, transparent);
}

.message.assistant + .message.assistant {
  margin-top: -8px;
}

.message.assistant + .message.assistant .message-author {
  display: none;
}

.remember-message {
  gap: 4px;
  padding: 0 6px;
  color: var(--muted);
  font-size: 10px;
}

.remember-message:hover {
  color: var(--accent);
}

:global(.font-small) .bubble {
  font-size: 13px;
}

:global(.font-large) .bubble {
  font-size: 18px;
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 160px;
  padding: 24px;
  color: var(--muted);
  text-align: center;
}

.empty h2,
.empty p {
  margin: 0;
}

.welcome {
  min-height: 100%;
  gap: 8px;
  opacity: 0.72;
}

.welcome-mark {
  color: var(--accent);
  font-size: 17px;
  line-height: 1;
}

.welcome small {
  font-size: 8px;
  font-weight: 600;
  letter-spacing: var(--type-eyebrow-tracking);
}

.welcome h2 {
  color: var(--text);
  font-size: 18px;
  font-weight: 540;
  line-height: 1.65;
  letter-spacing: 0.05em;
}

.welcome p {
  font-size: 12px;
}

.turn-time {
  display: block;
  margin: 10px 0 13px;
  color: color-mix(in srgb, var(--muted) 70%, transparent);
  font-size: 9px;
  letter-spacing: 0.03em;
  text-align: center;
}

.source-turn {
  border-radius: 12px;
  outline: 1px solid var(--accent);
  outline-offset: 8px;
  scroll-margin: 20px;
}

.load-older {
  display: flex;
  margin: 0 auto 20px;
  color: var(--muted);
  font-size: 12px;
}

.turn-status,
.chat-error {
  color: var(--accent);
  font-size: 12px;
  line-height: 1.8;
}

.turn-status {
  margin-bottom: 20px;
}

.reply-wait {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--muted);
}

.reply-wait > span {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--accent);
  animation: pulse 1s infinite alternate;
}

.reply-wait > span:nth-child(2) {
  animation-delay: 0.2s;
}

.reply-wait > span:nth-child(3) {
  animation-delay: 0.4s;
}

.reply-wait small {
  margin-left: 6px;
}

.composer {
  flex-shrink: 0;
  padding: 10px clamp(22px, 3vw, 38px) 18px;
}

.chat-error {
  padding-bottom: 9px;
}

.input-shell {
  display: flex;
  align-items: flex-end;
  gap: 9px;
  min-height: 58px;
  padding: 9px 9px 9px 18px;
  border: 1px solid rgba(255, 255, 255, 0.56);
  border-radius: 25px;
  background: rgba(255, 255, 255, 0.68);
  box-shadow: 0 10px 28px color-mix(in srgb, var(--text) 8%, transparent);
  backdrop-filter: blur(8px) saturate(1.06);
  transition:
    border-color 0.2s,
    background 0.2s,
    box-shadow 0.2s;
}

.input-shell:focus-within {
  border-color: color-mix(in srgb, var(--accent) 36%, #fff);
  background: #ffffff8f;
  box-shadow: 0 12px 30px color-mix(in srgb, var(--accent) 14%, transparent);
}

.input-shell textarea {
  flex: 1;
  min-width: 0;
  max-height: 150px;
  padding: 0;
  border: 0;
  outline: none;
  resize: none;
  background: none;
  color: var(--text);
  line-height: 1.7;
  font-size: var(--type-body-size);
}

.input-shell textarea::placeholder {
  color: color-mix(in srgb, var(--muted) 78%, transparent);
}

.send-button {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border-radius: 50%;
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--primary) 88%, #fff),
    color-mix(in srgb, var(--accent) 82%, #fff)
  );
  color: white;
  box-shadow: 0 6px 18px color-mix(in srgb, var(--accent) 22%, transparent);
}

.send-button:disabled {
  background: var(--soft);
  color: var(--muted);
  box-shadow: none;
}

.send-button img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.composer-caption {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 5px 0;
  color: color-mix(in srgb, var(--text) 60%, transparent);
  font-size: 9px;
  letter-spacing: 0.02em;
  text-shadow: 0 1px 8px #fff;
}

@media (max-width: 900px) {
  .chat-glass {
    right: 18px;
    width: min(64%, 620px);
  }

  .chat-header {
    margin-inline: 22px;
  }

  .messages {
    padding-inline: 24px;
  }

  .composer {
    padding-inline: 22px;
  }

  .avatar-note {
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

@media (max-width: 700px) {
  .chat-glass {
    top: calc(var(--chat-header-height) + 6px);
    right: 10px;
    bottom: 10px;
    left: 10px;
    width: auto;
    border-radius: 18px;
  }

  .chat-header {
    height: 72px;
    margin-inline: 18px;
  }

  .chat-header nav button:first-child {
    display: none;
  }

  .messages {
    padding: 20px 18px 12px;
  }

  .composer {
    padding: 10px 14px 16px;
  }

  .composer-caption span:last-child {
    display: none;
  }

  .atmosphere-copy {
    display: none;
  }
}
</style>
