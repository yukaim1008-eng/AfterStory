<script setup lang="ts">
import { computed } from "vue";
import {
  ArrowRight,
  BookOpen,
  Heart,
  MessageCircle,
  UsersRound,
  Sparkles,
  Settings2,
  LoaderCircle,
} from "lucide-vue-next";
import { useAfterStory } from "../composables/useAfterStory";
import { excerpt, displayTime } from "../presentation";
import Portrait from "../Portrait.vue";
import CharacterAvatar from "../components/CharacterAvatar.vue";
const {
  character,
  characters,
  chat,
  cover,
  covers,
  selected,
  connected,
  route,
  choose,
  memories,
  memoryLoading,
  memoryError,
  openChat,
} = useAfterStory();
const others = computed(() =>
  characters.value.filter((c) => c.id !== selected.value).slice(0, 3),
);
const heroVisual = computed(() => {
  const c = character.value;
  if (!c)
    return { source: "", crop: { x: 50, y: 50, zoom: 1 }, position: undefined };
  const custom = covers[c.id];
  if (custom || !c.sceneBackground)
    return {
      source: cover(c).source,
      crop: cover(c).crop.chat,
      position: undefined,
    };
  return {
    source: c.sceneBackground,
    crop: { x: 50, y: 50, zoom: 1 },
    position: c.sceneBackgroundPosition,
  };
});
const homeGreeting = computed(
  () => character.value?.sceneDecorations?.homeGreeting || "欢迎回来。",
);
const latestTime = computed(() =>
  chat.value?.total
    ? chat.value.turns.at(-1)?.created_at ||
      chat.value.session?.last_activity_at
    : undefined,
);
const recent = computed(() => {
  const fragments = (chat.value?.turns || [])
    .filter((t) => t.status === "completed")
    .slice(-3)
    .map((t) => ({
      id: t.turn_id,
      kind: "chat",
      content:
        t.messages.find((m) => m.role === "user")?.text || "一起说过的话",
      time: t.created_at,
    }));
  const saved = memories.value.slice(0, 3).map((m) => ({
    id: m.memory_id,
    kind: "memory",
    content: m.content,
    time: m.updated_at,
  }));
  return [...saved, ...fragments]
    .sort(
      (a, b) =>
        (Date.parse(b.time || "") || 0) - (Date.parse(a.time || "") || 0),
    )
    .slice(0, 3);
});
</script>
<template>
  <main v-if="character" id="main-content" tabindex="-1" class="home-page">
    <section class="home-hero" aria-label="当前陪伴角色">
      <div class="home-art">
        <Portrait
          :key="selected"
          :source="heroVisual.source"
          :crop="heroVisual.crop"
          :position="heroVisual.position"
          :name="character.name"
        />
        <div class="home-art-caption">
          <span>{{ character.romanized }}</span>
          <p>{{ character.tagline || "故事之外，还有想和你说的话。" }}</p>
        </div>
      </div>
      <div class="home-welcome">
        <span class="eyebrow">WELCOME BACK</span>
        <h1>今天，想和你相见。<Heart class="heading-heart" :size="36" /></h1>
        <p class="muted">故事之外，总有人在这里等你。</p>
        <div class="last-meeting">
          <CharacterAvatar :character="character" :cover="cover(character)" />
          <div>
            <strong>{{ character.name }}</strong
            ><span>{{
              chat?.loading
                ? "正在找回上次相见…"
                : latestTime
                  ? `上次相见 · ${displayTime(latestTime)}`
                  : chat?.total
                    ? "上次相见 · 未记录时间"
                    : "从今天，留下第一段回忆。"
            }}</span>
          </div>
        </div>
        <button class="primary hero-action" @click="route('chat')">
          <MessageCircle :size="19" />继续和
          {{ character.name }} 聊天<ArrowRight :size="19" />
        </button>
        <button class="secondary hero-action" @click="route('memory')">
          <BookOpen :size="19" />看看她记得什么
        </button>
        <span :key="selected" class="welcome-footnote home-greeting">{{
          homeGreeting
        }}</span>
      </div>
    </section>
    <div class="home-middle">
      <section class="recent-panel" aria-label="最近留下的痕迹">
        <header class="panel-heading">
          <h2><Heart :size="21" />最近回忆</h2>
          <span>你们最近留下的痕迹。</span
          ><button @click="route('history')">
            查看全部<ArrowRight :size="15" />
          </button>
        </header>
        <div v-if="chat?.loading || memoryLoading" class="home-state">
          <LoaderCircle class="spin" :size="20" />正在找回你们的回忆…
        </div>
        <div
          v-else-if="chat?.error || memoryError"
          class="home-state"
          role="alert"
        >
          <p>{{ chat?.error || memoryError }}</p>
          <button :disabled="!connected" @click="openChat(selected)">
            重新加载
          </button>
        </div>
        <div v-else-if="!recent.length" class="home-state home-empty">
          <span class="empty-mark"><BookOpen :size="18" /></span>
          <div>
            <p>第一段回忆，还在等你们写下。</p>
            <small>从一句想告诉她的话开始。</small>
          </div>
          <button class="empty-action" @click="route('chat')">
            去开始聊天<ArrowRight :size="15" />
          </button>
        </div>
        <div v-else class="recent-grid">
          <button
            v-for="item in recent"
            :key="item.id"
            class="recent-card"
            @click="
              item.kind === 'memory'
                ? route('memory')
                : route('chat', chat?.id, item.id)
            "
          >
            <CharacterAvatar :character="character" :cover="cover(character)" />
            <div>
              <span class="recall-kind">{{
                item.kind === "memory" ? "她记得：" : character.name
              }}</span>
              <time>{{ displayTime(item.time) }}</time>
              <p>{{ excerpt(item.content, 68) }}</p>
            </div>
          </button>
        </div>
      </section>
      <section class="quick-panel" aria-label="快捷入口">
        <header class="panel-heading">
          <h2><Sparkles :size="21" />快捷入口</h2>
          <span>从这里，续写你们的故事。</span>
        </header>
        <div class="quick-grid">
          <button @click="route('chat')">
            <i><MessageCircle /></i>
            <div>
              <strong>继续上次对话</strong><small>回到熟悉的聊天</small>
            </div>
          </button>
          <button @click="route('history')">
            <i><BookOpen /></i>
            <div><strong>查看回忆</strong><small>翻看珍贵的瞬间</small></div>
          </button>
          <button @click="route('characters')">
            <i><UsersRound /></i>
            <div><strong>切换角色</strong><small>去见其他伙伴</small></div>
          </button>
          <button @click="route('memory')">
            <i><Settings2 /></i>
            <div>
              <strong>管理记忆</strong><small>让她记得更多关于你</small>
            </div>
          </button>
        </div>
      </section>
    </div>
    <section
      v-if="others.length"
      class="other-companions"
      aria-label="也可以去见"
    >
      <div class="other-heading">
        <h2><UsersRound :size="22" />也可以去见</h2>
        <p>不同的世界，同一份陪伴。</p>
      </div>
      <button
        v-for="c in others"
        :key="c.id"
        class="companion-link"
        @click="choose(c)"
      >
        <CharacterAvatar :character="c" :cover="cover(c)" />
        <div>
          <strong>{{ c.name }}</strong>
          <p>{{ c.tagline || excerpt(c.description, 28) }}</p>
        </div>
      </button>
      <button class="secondary all-characters" @click="route('characters')">
        查看全部角色<ArrowRight :size="18" />
      </button>
    </section>
    <footer class="page-footer">
      <span>AfterStory · 故事之外，与你相见。</span
      ><span>不同的世界，同一份心动。 ♡</span>
    </footer>
  </main>
</template>
<style scoped>
/* Home-only presentation: the shared Desktop viewport contract is unchanged. */
:global(.page-home .page-background) {
  background: #faf8f4;
}
:global(.page-home .page-background > img) {
  opacity: 0.055;
  filter: blur(36px) saturate(0.4);
}
:global(.page-home .ambient-light) {
  background: radial-gradient(ellipse at 25% 0%, #fff9, transparent 65%);
}
.home-page {
  max-width: 1800px;
  margin: 0 auto;
  color: #38312f;
}
.home-hero {
  min-height: 0;
  height: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(390px, 1fr);
  align-items: center;
  position: relative;
  isolation: isolate;
  overflow: hidden;
  border-radius: 26px;
  border: 1px solid #ffffffa8;
  background: linear-gradient(112deg, #eeeae3 0%, #f7f3ec 57%, #fcfaf6 100%);
  box-shadow: 0 16px 44px #332b2112;
}
.home-art {
  position: absolute;
  inset: 0 17% 0 0;
  z-index: -1;
  overflow: hidden;
  mask-image: linear-gradient(90deg, #000 0 58%, #000d 72%, transparent 95%);
}
.home-art :deep(.portrait) {
  background: transparent;
}
.home-art :deep(img) {
  object-fit: cover;
}
.home-art::after {
  content: "";
  position: absolute;
  inset: 0;
  background:
    linear-gradient(90deg, transparent 50%, #faf7f1b8 95%),
    linear-gradient(0deg, #211a265c, transparent 48%);
  pointer-events: none;
}
.home-art-caption {
  position: absolute;
  bottom: 28px;
  left: 32px;
  color: #fff;
  text-shadow: 0 2px 12px #211a2638;
  max-width: 340px;
  z-index: 1;
}
.home-art-caption span {
  font-size: 11px;
  letter-spacing: 0.35em;
}
.home-art-caption p {
  font-family: "Kaiti SC", "STKaiti", "KaiTi", serif;
  font-size: 20px;
  line-height: 1.6;
  margin: 10px 0 0;
}
.home-welcome {
  grid-column: 2;
  min-height: 0;
  max-height: 100%;
  position: relative;
  padding: 24px clamp(24px, 3vw, 48px) 24px clamp(20px, 2.6vw, 40px);
  background: linear-gradient(
    104deg,
    #fff0 0%,
    #fff4 26%,
    #fffc 70%,
    #ffff 100%
  );
  backdrop-filter: blur(2px);
}
.home-welcome::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 -34px;
  width: 64px;
  background: linear-gradient(90deg, transparent, #fff8);
  pointer-events: none;
}
.home-welcome .eyebrow {
  position: relative;
  color: var(--muted);
  font-size: 10px;
  margin-bottom: 16px;
}
.home-welcome h1 {
  position: relative;
  font-size: clamp(32px, 2.2vw, 42px);
  display: flex;
  align-items: center;
  gap: 12px;
  letter-spacing: -1px;
  line-height: 1.4;
  margin-bottom: 12px;
}
.heading-heart {
  color: var(--accent);
  transform: rotate(-14deg);
  flex-shrink: 0;
  opacity: 0.75;
}
.home-welcome > .muted {
  position: relative;
  font-size: 14px;
  margin-bottom: 0;
}
.last-meeting {
  position: relative;
  display: flex;
  gap: 12px;
  align-items: center;
  margin: 22px 0;
}
.last-meeting .character-avatar {
  width: 42px;
  height: 42px;
}
.last-meeting strong {
  display: block;
  font-size: 15px;
  margin-bottom: 4px;
}
.last-meeting span {
  font-size: 12px;
  color: var(--muted);
}
.hero-action {
  position: relative;
  width: 100%;
  max-width: 350px;
  margin-bottom: 10px;
  display: flex;
  padding-block: 11px;
  font-size: 14px;
}
.hero-action.secondary {
  background: #ffffff42;
  border-color: color-mix(in srgb, var(--accent) 16%, transparent);
  box-shadow: none;
}
.home-greeting {
  position: relative;
  display: block;
  font-family: "Kaiti SC", "STKaiti", "KaiTi", serif;
  color: color-mix(in srgb, var(--accent) 68%, var(--muted));
  font-size: 17px;
  line-height: 1.6;
  margin-top: 12px;
  margin-left: 6px;
  transform: rotate(-2deg);
  opacity: 0.75;
}
.home-middle {
  display: grid;
  grid-template-columns: minmax(0, 1.8fr) minmax(350px, 1fr);
  gap: 24px;
  align-items: start;
}
.recent-panel,
.quick-panel {
  min-width: 0;
  padding: 16px 20px;
  border-radius: 19px;
  background: linear-gradient(135deg, #ffffff72, #fffdfb3d);
  border: 1px solid #ffffffa8;
  box-shadow: 0 10px 28px #332b2109;
}
.recent-panel:has(.home-state) {
  align-self: start;
}
.panel-heading {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 14px;
}
.panel-heading h2,
.other-heading h2 {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 17px;
  margin: 0;
  white-space: nowrap;
}
.panel-heading h2 svg,
.other-heading svg {
  color: var(--accent);
  opacity: 0.65;
}
.panel-heading > span {
  font-size: 11px;
  color: var(--muted);
}
.panel-heading > button {
  margin-left: auto;
  font-size: 11px;
  color: var(--muted);
  white-space: nowrap;
  padding: 4px;
}
.recent-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0;
}
.recent-card {
  min-width: 0;
  text-align: left;
  justify-content: flex-start;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 0;
  background: transparent;
}
.recent-card + .recent-card {
  border-left: 1px solid #b3a99b26;
}
.recent-card:first-child {
  padding-left: 0;
}
.recent-card:hover {
  background: transparent;
  color: #38312f;
}
.recent-card:hover p {
  color: var(--accent);
}
.recent-card .character-avatar {
  width: 28px;
  height: 28px;
  margin-top: 2px;
  border-width: 1px;
}
.recent-card > div:last-child {
  min-width: 0;
}
.recall-kind {
  font-size: 12px;
  color: #4c4541;
}
.recent-card time {
  display: block;
  font-size: 10px;
  color: var(--muted);
  margin-top: 3px;
}
.recent-card p {
  font-size: 12px;
  line-height: 1.7;
  margin: 8px 0 0;
  color: var(--muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  transition: color 0.2s;
}
.home-state {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  min-height: 0;
  color: var(--muted);
  font-size: 13px;
}
.home-state p {
  margin: 0;
  font-size: 13px;
}
.home-empty {
  min-height: 0;
  padding: 11px 2px 1px;
}
.empty-mark {
  display: grid;
  width: 31px;
  height: 31px;
  place-items: center;
  border-radius: 10px 12px 9px 11px;
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 8%, transparent);
  opacity: 0.75;
  transform: rotate(-3deg);
  flex: 0 0 auto;
}
.home-empty > div {
  min-width: 0;
}
.home-empty small {
  display: block;
  margin-top: 3px;
  color: var(--muted);
  font-size: 11px;
}
.empty-action {
  margin-left: auto;
  padding: 5px 2px 5px 8px;
  color: var(--accent);
  font-size: 11px;
  white-space: nowrap;
}
.empty-action:hover {
  background: transparent;
  transform: translateX(2px);
}
.home-state[role="alert"] {
  flex-wrap: wrap;
}
.quick-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 12px;
}
.quick-grid button {
  min-width: 0;
  text-align: left;
  justify-content: flex-start;
  padding: 9px 6px;
  gap: 10px;
  border-radius: 11px 12px 10px 13px;
}
.quick-grid button:hover {
  background: color-mix(in srgb, var(--accent) 6%, #ffffff4a);
  transform: translateX(2px);
}
.quick-grid i {
  height: 30px;
  width: 30px;
  display: grid;
  place-items: center;
  color: var(--accent);
  flex-shrink: 0;
  opacity: 0.75;
  border: 1px solid color-mix(in srgb, var(--accent) 10%, transparent);
  border-radius: 10px 12px 9px 11px;
  background: color-mix(in srgb, var(--accent) 5%, transparent);
}
.quick-grid i svg {
  width: 20px;
  height: 20px;
}
.quick-grid strong {
  font-size: 12px;
  font-weight: 550;
}
.quick-grid small {
  display: block;
  font-size: 10px;
  margin-top: 3px;
  color: var(--muted);
}
.other-companions {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 14px;
  border: 1px solid #ffffff9a;
  border-radius: 18px 20px 17px 19px;
  background: linear-gradient(100deg, #ffffff60, #fffdfb2e);
  box-shadow: 0 8px 24px #332b2108;
}
.other-heading {
  margin-right: 8px;
  min-width: 165px;
  flex-shrink: 0;
}
.other-heading h2 {
  font-size: 15px;
}
.other-heading p {
  font-size: 11px;
  color: var(--muted);
  margin: 5px 0 0;
}
.companion-link {
  text-align: left;
  gap: 10px;
  max-width: 270px;
  min-width: 0;
  padding: 8px 10px;
  border-radius: 12px 14px 11px 13px;
  border: 1px solid transparent;
}
.companion-link .character-avatar {
  width: 34px;
  height: 34px;
}
.companion-link:hover {
  background: #ffffff8c;
  border-color: color-mix(in srgb, var(--accent) 10%, transparent);
  transform: translateY(-1px);
}
.companion-link strong {
  font-size: 12px;
  font-weight: 550;
}
.companion-link p {
  font-size: 11px;
  color: var(--muted);
  margin: 3px 0 0;
}
.all-characters.secondary {
  white-space: nowrap;
  flex-shrink: 0;
  padding: 7px 8px;
  background: #ffffff2e;
  border: 1px solid #ffffff80;
  border-radius: 10px 12px 9px 11px;
  font-size: 12px;
  color: var(--muted);
}
.all-characters:hover {
  color: var(--accent);
}
@media (min-width: 761px) {
  .home-page {
    width: 100%;
    height: calc(100dvh - var(--desktop-header-height));
    padding-block: var(--page-padding-y);
    display: grid;
    grid-template-rows: minmax(0, 1fr) auto auto auto;
    gap: var(--page-gap);
  }
  .page-footer {
    width: 100%;
    margin: 0;
    font-size: 10px;
    opacity: 0.65;
  }
}
@media (min-width: 1151px) and (max-height: 800px) {
  .home-welcome {
    padding-block: 13px;
  }
  .home-welcome .eyebrow {
    margin-bottom: 10px;
  }
  .home-welcome h1 {
    font-size: 30px;
    line-height: 1.28;
    margin-bottom: 6px;
  }
  .last-meeting {
    margin: 12px 0;
  }
  .hero-action {
    padding-block: 7px;
    margin-bottom: 6px;
  }
  .home-greeting {
    font-size: 15px;
    line-height: 1.35;
    margin-top: 4px;
  }
  .home-art-caption {
    bottom: 20px;
  }
}
@media (max-width: 1150px) {
  .home-middle {
    grid-template-columns: 1fr;
    gap: 12px;
  }
  .quick-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
  .other-companions {
    flex-wrap: wrap;
    gap: 12px;
  }
  .panel-heading > span {
    display: none;
  }
}
@media (max-width: 760px) {
  .home-hero {
    grid-template-columns: 1fr;
    height: auto;
    padding-top: 240px;
  }
  .home-art {
    inset: 0 0 auto;
    height: 320px;
    mask-image: linear-gradient(#000 60%, transparent);
  }
  .home-welcome {
    grid-column: 1;
    padding: 24px;
  }
  .home-art-caption {
    display: none;
  }
  .quick-grid {
    grid-template-columns: 1fr 1fr;
  }
  .recent-grid {
    grid-template-columns: 1fr;
  }
  .recent-card + .recent-card {
    border-left: 0;
    border-top: 1px solid #b3a99b26;
  }
  .recent-card {
    padding: 12px 0;
  }
  .other-heading {
    width: 100%;
  }
}
</style>
