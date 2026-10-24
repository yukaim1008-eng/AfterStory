<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { ArrowUp, LoaderCircle, Plus } from "lucide-vue-next";
import { useAfterStory } from "../composables/useAfterStory";
import CharacterAvatar from "../components/CharacterAvatar.vue";
import type { Character } from "../types";

const props = defineProps<{ character: Character; mobile: boolean }>();
const {
  chat,
  cover,
  connected,
  capabilities,
  targetTurn,
  selected,
  scrollArea,
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
const showLatest = ref(false);
const composerInput = ref<HTMLTextAreaElement>();

function updateLatest() {
  const area = scrollArea.value;
  showLatest.value =
    !!area && area.scrollHeight - area.clientHeight - area.scrollTop > 56;
}
function scrollToLatest() {
  const area = scrollArea.value;
  area?.scrollTo({ top: area.scrollHeight, behavior: "smooth" });
  showLatest.value = false;
}
function resizeComposer() {
  const input = composerInput.value;
  if (!input) return;
  if (!props.mobile) {
    input.style.height = "";
    return;
  }
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 104)}px`;
}
function handleInput() {
  saveChat(selected.value);
  resizeComposer();
}
function handleInputKey(event: KeyboardEvent) {
  if (!props.mobile) inputKey(event);
}
async function sendFromComposer() {
  try {
    const sending = send();
    await nextTick();
    const area = scrollArea.value;
    if (area) area.scrollTop = area.scrollHeight;
    await sending;
  } finally {
    await nextTick();
    resizeComposer();
  }
}
watch(
  () => chat.value?.draft,
  async () => {
    await nextTick();
    resizeComposer();
  },
);
onMounted(() => {
  resizeComposer();
  window.visualViewport?.addEventListener("resize", resizeComposer);
  window.addEventListener("resize", resizeComposer);
});
onUnmounted(() => {
  window.visualViewport?.removeEventListener("resize", resizeComposer);
  window.removeEventListener("resize", resizeComposer);
});
</script>

<template>
  <div
    ref="scrollArea"
    class="messages"
    :class="{ 'desktop-messages': !mobile }"
    aria-live="polite"
    :aria-busy="chat?.loading"
    @scroll.passive="updateLatest"
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
      <template v-if="mobile">
        <span class="welcome-mark" aria-hidden="true">✳</span>
        <h2>今天想和{{ character.name }}聊些什么？</h2>
        <p>从一件小事开始也好。</p>
      </template>
      <template v-else>
        <span class="welcome-mark">✳</span>
        <small>ANOTHER DAY, ANOTHER STORY</small>
        <h2>故事之外，<br />还有话想对你说。</h2>
        <p>从今天的一件小事开始吧。</p>
      </template>
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
        <div class="message-body">
          <CharacterAvatar
            v-if="message.role === 'assistant'"
            :character="character"
            :cover="cover(character)"
          />
          <div class="bubble">{{ message.text }}</div>
        </div>
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
        !chat.turns.some((turn) => turn.request_id === chat.pending?.request_id)
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

  <button
    v-if="mobile && showLatest"
    class="back-to-latest"
    type="button"
    @click="scrollToLatest"
  >
    <ArrowUp :size="16" aria-hidden="true" />回到最新
  </button>

  <form class="composer" @submit.prevent="sendFromComposer">
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
        ref="composerInput"
        v-model="chat.draft"
        aria-label="消息"
        :placeholder="`想和${character.name}说些什么……`"
        maxlength="8000"
        rows="2"
        :disabled="!connected"
        @input="handleInput"
        @keydown="handleInputKey"
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
  </form>
</template>

<style scoped>
.messages {
  position: relative;
  z-index: 7;
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

.message-body {
  display: contents;
}

.desktop-messages .message.assistant .message-author {
  margin-left: 52px;
}

.desktop-messages .message.assistant .message-body {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 100%;
}

.desktop-messages .message.assistant .message-body :deep(.character-avatar) {
  box-sizing: border-box;
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  box-shadow: 0 4px 14px color-mix(in srgb, var(--accent) 17%, transparent);
}

.desktop-messages .message.assistant .message-body .bubble {
  min-width: 0;
  max-width: min(calc(100% - 46px), 640px);
  padding: 11px 15px;
  border: 1px solid rgba(255, 255, 255, 0.74);
  border-left: 2px solid color-mix(in srgb, var(--accent) 52%, white);
  border-radius: 6px 17px 17px 17px;
  background: rgba(255, 253, 252, 0.84);
  box-shadow: 0 6px 22px color-mix(in srgb, var(--text) 10%, transparent);
  font-family: var(--font-ui);
  font-size: 15px;
  line-height: 1.68;
  letter-spacing: 0;
}

:global(.font-small) .desktop-messages .message.assistant .message-body .bubble {
  font-size: 13px;
}

:global(.font-large) .desktop-messages .message.assistant .message-body .bubble {
  font-size: 18px;
}

.desktop-messages .message.assistant + .message.assistant .character-avatar {
  visibility: hidden;
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

.message.assistant .bubble {
  font-family: var(--font-character);
  letter-spacing: 0.025em;
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
  position: relative;
  z-index: 7;
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
</style>
