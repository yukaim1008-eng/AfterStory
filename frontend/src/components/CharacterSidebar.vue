<script setup lang="ts">
import { BookHeart, BookOpen, ImagePlus, MessageCircle } from "lucide-vue-next";
import { useAfterStory } from "../composables/useAfterStory";
import Portrait from "../Portrait.vue";

withDefaults(defineProps<{ compact?: boolean }>(), { compact: false });

const { character, cover, route, connected, editing, page } = useAfterStory();
</script>

<template>
  <aside
    v-if="character"
    class="character-sidebar"
    :class="{ compact }"
    :aria-label="`${character.name}的角色空间`"
  >
    <div class="sidebar-art">
      <Portrait
        :source="cover(character).source"
        :crop="cover(character).crop.chat"
        :name="character.name"
      />
      <div class="sidebar-gradient"></div>
    </div>

    <div class="sidebar-content">
      <small>{{ character.world }} · {{ character.romanized }}</small>
      <h1>{{ character.name }}</h1>
      <p>{{ character.tagline || character.description }}</p>

      <nav aria-label="角色空间导航">
        <button :class="{ active: page === 'chat' }" @click="route('chat')">
          <MessageCircle :size="17" />与她聊天
        </button>
        <button
          :class="{ active: page === 'history' || page === 'memory' }"
          aria-label="查看角色回忆"
          @click="route('history')"
        >
          <BookHeart :size="17" />回忆
        </button>
        <button
          :class="{ active: page === 'profile' }"
          @click="route('profile')"
        >
          <BookOpen :size="17" />角色资料
        </button>
      </nav>

      <button
        class="cover-action"
        aria-label="更换封面"
        :disabled="!connected"
        @click="editing = true"
      >
        <ImagePlus :size="16" />更换封面
      </button>
    </div>
  </aside>
</template>

<style scoped>
.character-sidebar {
  position: relative;
  min-width: 0;
  overflow: hidden;
  background: var(--soft);
  color: white;
}

.character-sidebar::after {
  content: none;
}

.sidebar-art,
.sidebar-art :deep(.portrait) {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  border-radius: 0;
}

.sidebar-art :deep(img) {
  transition: scale 0.5s ease;
}

.character-sidebar:hover .sidebar-art :deep(img) {
  scale: 1.015;
}

.sidebar-gradient {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, #15101c0a 28%, #17101cbf 76%, #130e19e8),
    linear-gradient(
      90deg,
      transparent 75%,
      color-mix(in srgb, var(--soft) 32%, transparent)
    );
}

.sidebar-content {
  position: absolute;
  z-index: 1;
  right: clamp(24px, 4vw, 58px);
  bottom: clamp(28px, 5vh, 58px);
  left: clamp(24px, 4vw, 58px);
  color: white;
}

.sidebar-content > small {
  color: #ffffffbd;
  font-size: 10px;
  letter-spacing: 3px;
}

.sidebar-content h1 {
  margin: 9px 0 10px;
  color: white;
  font-size: clamp(34px, 3vw, 50px);
  letter-spacing: 3px;
}

.sidebar-content > p {
  max-width: 34ch;
  margin: 0 0 20px;
  color: #ffffffe0;
  font-size: 12px;
  line-height: 1.8;
}

.sidebar-content nav {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.sidebar-content nav button,
.cover-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 9px 13px;
  border: 1px solid #ffffff47;
  border-radius: 99px;
  background: #21182c66;
  color: white;
  font-size: 11px;
  backdrop-filter: blur(12px);
}

.sidebar-content nav button:hover,
.sidebar-content nav button:focus-visible,
.cover-action:hover:not(:disabled),
.cover-action:focus-visible {
  background: #ffffff29;
  color: white;
}

.sidebar-content nav button.active {
  border-color: #ffffffc4;
  background: #ffffffdf;
  color: var(--accent) !important;
}

.cover-action {
  margin-top: 10px;
}

.cover-action:disabled {
  opacity: 0.5;
}

.compact .sidebar-content > p,
.compact .sidebar-content nav button span {
  display: none;
}

@media (max-width: 900px) {
  .sidebar-content {
    right: 24px;
    bottom: 28px;
    left: 24px;
  }

  .sidebar-content > p {
    display: none;
  }
}

@media (max-width: 700px) {
  .character-sidebar {
    display: none;
  }
}
</style>
