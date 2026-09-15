<script setup lang="ts">
import { computed } from "vue";
import { ArrowUp, BookOpen, LoaderCircle, Plus } from "lucide-vue-next";
import { useAfterStory } from "../composables/useAfterStory";
import CharacterAvatar from "../components/CharacterAvatar.vue";
import ChatCharacterScene from "../components/ChatCharacterScene.vue";

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
      <header class="chat-header">
        <CharacterAvatar :character="character" :cover="cover(character)" />
        <div>
          <h2>{{ character.name }}</h2>
          <span><i :class="{ online: connected }"></i>{{ presence }}</span>
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
  position: relative;
  width: 100%;
  max-width: 1800px;
  height: min(900px, calc(100dvh - 116px));
  min-height: 570px;
  margin: auto;
  overflow: hidden;
  border: 1px solid #ffffff9e;
  border-radius: clamp(22px, 2vw, 32px);
  background: var(--background);
  box-shadow:
    0 26px 80px color-mix(in srgb, var(--text) 13%, transparent),
    inset 0 1px #ffffffb8;
}

.chat-glass {
  position: absolute;
  z-index: 4;
  top: clamp(18px, 3vh, 32px);
  right: clamp(18px, 2.4vw, 38px);
  bottom: clamp(18px, 3vh, 32px);
  width: clamp(540px, 53%, 780px);
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #ffffffc2;
  border-radius: clamp(20px, 2vw, 30px);
  background: linear-gradient(
    145deg,
    var(--glass-surface-strong),
    var(--glass-surface) 52%,
    color-mix(in srgb, var(--soft) 16%, rgba(255, 255, 255, 0.5))
  );
  box-shadow:
    0 24px 70px color-mix(in srgb, var(--text) 14%, transparent),
    inset 0 1px #ffffffc7;
  backdrop-filter: blur(18px) saturate(1.12);
  -webkit-backdrop-filter: blur(18px) saturate(1.12);
}

.chat-header {
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 12px;
  min-height: 82px;
  margin: 0 clamp(22px, 3vw, 38px);
  border-bottom: 1px solid #ffffff8f;
}

.chat-header .character-avatar {
  width: 42px;
  height: 42px;
  box-shadow: 0 8px 24px color-mix(in srgb, var(--accent) 16%, transparent);
}

.chat-header h2 {
  margin: 0 0 4px;
  font-size: var(--type-section-size);
  font-weight: 650;
  line-height: 1.2;
  letter-spacing: 0.05em;
}

.chat-header span {
  color: var(--muted);
  font-size: var(--type-caption-size);
  letter-spacing: 0.04em;
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
  color: color-mix(in srgb, var(--text) 72%, transparent);
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
  padding: 24px clamp(24px, 3vw, 40px) 16px;
  scrollbar-width: thin;
  scrollbar-color: var(--soft) transparent;
}

.message {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 7px;
  margin: 0 0 19px;
}

.message.user {
  align-items: flex-end;
}

.message-author {
  margin: 0 6px;
  color: var(--muted);
  font-size: var(--type-caption-size);
  letter-spacing: 0.04em;
}

.bubble {
  max-width: min(86%, 640px);
  padding: 11px 16px;
  border: 1px solid #ffffffb0;
  border-radius: 5px 18px 18px;
  background: #ffffff8f;
  box-shadow: 0 7px 22px #34232d0b;
  color: var(--text);
  font-size: var(--type-body-size);
  font-weight: 430;
  line-height: 1.82;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.message.user .bubble {
  border: 1px solid color-mix(in srgb, var(--accent) 8%, transparent);
  border-radius: 18px 5px 18px 18px;
  background: color-mix(in srgb, var(--soft) 68%, #ffffffad);
  box-shadow: none;
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
  gap: 9px;
  opacity: 0.88;
}

.welcome-mark {
  color: var(--accent);
  font-size: 20px;
  line-height: 1;
}

.welcome small {
  font-size: 8px;
  font-weight: 600;
  letter-spacing: var(--type-eyebrow-tracking);
}

.welcome h2 {
  color: var(--text);
  font-size: 20px;
  font-weight: 580;
  line-height: 1.6;
  letter-spacing: 0.04em;
}

.welcome p {
  font-size: 12px;
}

.turn-time {
  display: block;
  margin: 13px 0 17px;
  color: var(--muted);
  font-size: var(--type-caption-size);
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
  padding: 11px clamp(22px, 3vw, 38px) 20px;
}

.chat-error {
  padding-bottom: 9px;
}

.input-shell {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 11px 11px 11px 19px;
  border: 1px solid #ffffffd1;
  border-radius: 26px;
  background: #ffffffa8;
  box-shadow: 0 12px 34px color-mix(in srgb, var(--text) 9%, transparent);
  backdrop-filter: blur(14px);
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
  line-height: 1.8;
  font-size: var(--type-body-size);
}

.input-shell textarea::placeholder {
  color: var(--muted);
}

.send-button {
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), var(--accent));
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
  padding: 10px 5px 0;
  color: color-mix(in srgb, var(--text) 70%, transparent);
  font-size: var(--type-caption-size);
  letter-spacing: 0.02em;
  text-shadow: 0 1px 8px #fff;
}

@media (max-width: 900px) {
  .chat-glass {
    width: min(63%, 620px);
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
}

@media (max-width: 700px) {
  .chat-workspace {
    height: calc(100dvh - 78px);
    min-height: 500px;
    border-radius: 18px;
  }

  .chat-glass {
    inset: 10px;
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
}
</style>
