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
import GlassPanel from "../components/GlassPanel.vue";
import CharacterAvatar from "../components/CharacterAvatar.vue";
const {
  character,
  characters,
  chat,
  cover,
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
      title: excerpt(
        t.messages.find((m) => m.role === "user")?.text || "一起说过的话",
        24,
      ),
      content: t.messages.find((m) => m.role === "assistant")?.text || "",
      time: t.created_at,
    }));
  const saved = memories.value.slice(0, 3).map((m) => ({
    id: m.memory_id,
    kind: "memory",
    title: "她记得的事",
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
          :source="cover(character).source"
          :crop="cover(character).crop.chat"
          :name="character.name"
        />
        <div class="home-art-caption">
          <span>{{ character.romanized }}</span>
          <p>{{ character.tagline || "故事之外，还有想和你说的话。" }}</p>
        </div>
      </div>
      <GlassPanel class="home-welcome">
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
        <span class="welcome-footnote">把今天的小事，慢慢说给她听。</span>
      </GlassPanel>
    </section>
    <div class="home-middle">
      <GlassPanel class="recent-panel">
        <header class="panel-heading">
          <h2><Heart :size="21" />最近回忆</h2>
          <span>那些我们一起度过的时光。</span
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
        <div v-else-if="!recent.length" class="home-state">
          <BookOpen :size="26" />
          <div>
            <strong>回忆，从一句话开始</strong>
            <p>聊过的片段、你希望她记住的事，都会慢慢留在这里。</p>
          </div>
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
            <Portrait
              :source="cover(character).source"
              :crop="cover(character).crop.chat"
              :name="character.name"
            />
            <div>
              <span class="recall-kind">{{
                item.kind === "memory" ? "她记得的事" : "聊天片段"
              }}</span>
              <h3>{{ item.title }}</h3>
              <p>{{ excerpt(item.content, 54) }}</p>
              <time>{{ displayTime(item.time) }}</time>
            </div>
          </button>
        </div>
      </GlassPanel>
      <GlassPanel class="quick-panel">
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
      </GlassPanel>
    </div>
    <GlassPanel v-if="others.length" class="other-companions">
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
    </GlassPanel>
    <footer class="page-footer">
      <span>AfterStory · 故事之外，与你相见。</span
      ><span>不同的世界，同一份心动。 ♡</span>
    </footer>
  </main>
</template>
<style scoped>
.home-page {
  max-width: 1800px;
  margin: 0 auto;
}
.home-hero {
  min-height: 0;
  height: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(390px, 1fr);
  align-items: center;
  position: relative;
}
.home-art {
  position: absolute;
  inset: -12px 30% -25px -3vw;
  overflow: hidden;
  z-index: -1;
  mask-image:
    linear-gradient(90deg, #000 65%, transparent),
    linear-gradient(0deg, transparent, #000 15%);
  mask-composite: intersect;
}
.home-art .portrait {
  background: transparent;
}
.home-art img {
  object-position: 50% 28%;
}
.home-art-caption {
  position: absolute;
  bottom: 54px;
  left: 8%;
  color: white;
  text-shadow: 0 2px 14px #281426;
  max-width: 370px;
}
.home-art-caption span {
  font-size: 11px;
  letter-spacing: 5px;
}
.home-art-caption p {
  font-size: 22px;
  margin: 10px 0 0;
}
.home-welcome {
  grid-column: 2;
  padding: 20px 24px;
  background: color-mix(in srgb, var(--surface) 88%, transparent);
}
.home-welcome h1 {
  font-size: clamp(32px, 2.2vw, 42px);
  display: flex;
  align-items: center;
  gap: 14px;
  letter-spacing: -1px;
}
.heading-heart {
  color: var(--accent);
  transform: rotate(-14deg);
  flex-shrink: 0;
}
.last-meeting {
  display: flex;
  gap: 14px;
  align-items: center;
  margin: 16px 0;
}
.last-meeting strong {
  display: block;
  font-size: 15px;
  margin-bottom: 6px;
}
.last-meeting span {
  font-size: 12px;
  color: var(--muted);
}
.hero-action {
  width: 100%;
  max-width: 360px;
  margin-bottom: 10px;
  display: flex;
  font-size: 14px;
}
.welcome-footnote {
  display: block;
  color: var(--muted);
  font-size: 11px;
  margin-top: 8px;
}
.home-middle {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(330px, 1fr);
  gap: 20px;
}
.recent-panel,
.quick-panel {
  padding: 16px;
}
.panel-heading {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}
.panel-heading h2,
.other-heading h2 {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  margin: 0;
  white-space: nowrap;
}
.panel-heading h2 svg,
.other-heading svg {
  color: var(--accent);
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
}
.recent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}
.recent-card {
  text-align: left;
  justify-content: flex-start;
  align-items: stretch;
  gap: 12px;
  padding: 12px;
  background: #ffffff87;
  border-radius: 16px;
  min-width: 0;
}
.recent-card > .portrait {
  width: 66px;
  height: auto;
  min-height: 90px;
  border-radius: 10px;
  flex-shrink: 0;
}
.recent-card > div:last-child {
  min-width: 0;
}
.recent-card h3 {
  font-size: 12px;
  line-height: 1.7;
  margin: 3px 0;
}
.recent-card p {
  font-size: 11px;
  line-height: 1.8;
  color: var(--muted);
  margin: 4px 0 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.recent-card time,
.recall-kind {
  font-size: 10px;
  color: var(--muted);
}
.recall-kind {
  color: var(--accent);
}
.home-state {
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 18px;
  color: var(--muted);
  font-size: 13px;
}
.home-state p {
  margin: 5px 0 0;
  font-size: 12px;
}
.quick-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.quick-grid button {
  text-align: left;
  justify-content: flex-start;
  background: #ffffff87;
  border-radius: 15px;
  padding: 12px;
  gap: 12px;
}
.quick-grid i {
  height: 40px;
  width: 40px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--soft) 65%, transparent);
  display: grid;
  place-items: center;
  color: var(--accent);
  flex-shrink: 0;
}
.quick-grid strong {
  font-size: 12px;
}
.quick-grid small {
  display: block;
  font-size: 10px;
  margin-top: 5px;
}
.other-companions {
  margin-top: 0;
  padding: 14px 20px;
  display: flex;
  align-items: center;
  gap: 20px;
}
.other-heading {
  margin-right: auto;
  flex-shrink: 0;
}
.other-heading p {
  font-size: 11px;
  color: var(--muted);
  margin: 7px 0 0;
}
.companion-link {
  text-align: left;
  gap: 12px;
  max-width: 260px;
  min-width: 0;
}
.companion-link strong {
  font-size: 13px;
}
.companion-link p {
  font-size: 11px;
  color: var(--muted);
  margin: 5px 0 0;
}
.all-characters {
  white-space: nowrap;
  flex-shrink: 0;
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
  .home-welcome {
    max-height: 100%;
    min-height: 0;
  }
  .hero-action {
    padding-block: 10px;
  }
  .page-footer {
    width: 100%;
    margin: 0;
  }
}
@media (min-width: 1151px) and (max-height: 800px) {
  .home-welcome {
    padding: 12px 20px;
  }
  .home-welcome .eyebrow {
    margin-bottom: 10px;
  }
  .home-welcome h1 {
    font-size: 32px;
    margin-bottom: 8px;
  }
  .home-welcome > .muted {
    margin-bottom: 8px;
  }
  .last-meeting {
    margin: 12px 0;
  }
  .hero-action {
    margin-bottom: 6px;
    padding-block: 8px;
  }
  .welcome-footnote {
    margin-top: 4px;
  }
  .recent-card > .portrait {
    min-height: 80px;
  }
  .recent-card p {
    margin-bottom: 6px;
  }
  .quick-grid button {
    padding: 10px;
  }
  .other-companions {
    padding-block: 10px;
  }
}
@media (min-width: 1600px) {
  .recent-card > .portrait {
    width: 84px;
  }
  .recent-card h3 {
    font-size: 14px;
  }
  .recent-card p {
    font-size: 12px;
  }
}
@media (max-width: 1150px) {
  .home-middle {
    grid-template-columns: 1fr;
  }
  .quick-grid {
    grid-template-columns: repeat(4, 1fr);
  }
  .other-companions {
    flex-wrap: wrap;
  }
  .home-art-caption {
    max-width: 220px;
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
    height: 350px;
    border-radius: 24px;
    mask-image: linear-gradient(#000 65%, transparent);
  }
  .home-welcome {
    grid-column: 1;
  }
  .home-art-caption {
    display: none;
  }
  .quick-grid {
    grid-template-columns: 1fr 1fr;
  }
  .panel-heading > span {
    display: none;
  }
  .other-heading {
    width: 100%;
  }
}
</style>
