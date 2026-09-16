<script setup lang="ts">
import { computed } from "vue";
import { ArrowRight, Crown, Heart } from "lucide-vue-next";
import type { Character, Cover } from "../types";
import { themeStyle } from "../theme";
import Portrait from "../Portrait.vue";

const props = defineProps<{
  character: Character;
  cover: Cover;
  current?: boolean;
  featured?: boolean;
}>();

const emit = defineEmits<{ select: [] }>();

const signature = computed(
  () =>
    props.character.sceneDecorations?.signature?.text ||
    props.character.tagline ||
    props.character.description,
);
</script>

<template>
  <button
    class="character-panel character-card"
    :class="[{ featured, current }, `character-${character.id}`]"
    :style="themeStyle(character)"
    :aria-label="`${current ? '继续和' : '去见'}${character.name}`"
    @click="emit('select')"
  >
    <div class="card-art">
      <Portrait
        :source="cover.source"
        :crop="cover.crop.selection"
        :name="character.name"
      />
    </div>

    <div class="card-content">
      <span v-if="current" class="current-badge"
        ><Crown :size="14" />当前角色</span
      >
      <Heart v-else class="card-heart" :size="18" />
      <small class="romanized">{{ character.romanized }}</small>
      <h2>{{ character.name }}</h2>
      <p class="tagline">{{ signature }}</p>
      <div v-if="!featured && character.tags?.length" class="tag-list">
        <span v-for="tag in character.tags" :key="tag">{{ tag }}</span>
      </div>
      <span class="visit-action"
        >{{ current ? "继续和她聊天" : "去见她的故事" }}<ArrowRight :size="17"
      /></span>
    </div>
  </button>
</template>

<style scoped>
.character-panel.character-card {
  --card-tint: color-mix(in srgb, var(--secondary) 50%, white);
  box-sizing: border-box;
  display: block;
  width: 100%;
  min-width: 0;
  height: 100%;
  min-height: 0;
  flex: none;
  position: relative;
  isolation: isolate;
  padding: 0;
  overflow: hidden;
  border: 1px solid #ffffffd9;
  border-radius: 22px 25px 21px 24px;
  background: var(--card-tint);
  box-shadow: 0 14px 42px color-mix(in srgb, var(--text) 7%, transparent);
  color: var(--text);
  text-align: left;
  transition:
    transform 0.25s ease,
    box-shadow 0.25s ease,
    border-color 0.25s ease;
}

.character-panel.character-card::after {
  content: none;
  position: static;
  inset: auto;
  background: none;
}

.character-panel.character-card:hover,
.character-panel.character-card:focus-visible {
  flex: none;
  transform: translateY(-2px);
  border-color: color-mix(in srgb, var(--accent) 30%, white);
  box-shadow: 0 18px 48px color-mix(in srgb, var(--accent) 14%, transparent);
}

.character-nanally:hover,
.character-nanally:focus-visible {
  transform: translateY(-3px) rotate(-0.15deg);
  box-shadow: 0 20px 54px #cf397938;
}

.character-iroi:hover,
.character-iroi:focus-visible {
  transform: translateY(-1px);
  box-shadow: 0 16px 42px #507c6820;
}

.character-mint:hover,
.character-mint:focus-visible {
  transform: translateY(-4px) rotate(0.15deg);
  box-shadow: 0 21px 52px #167e8830;
}

.character-panel.character-card:focus-visible {
  outline: 3px solid color-mix(in srgb, var(--accent) 38%, transparent);
  outline-offset: 3px;
}

.card-art {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.card-art::after {
  content: "";
  position: absolute;
  inset: 0;
  background:
    linear-gradient(
      90deg,
      transparent 22%,
      color-mix(in srgb, var(--card-tint) 48%, transparent) 53%,
      color-mix(in srgb, var(--card-tint) 86%, #ffffffaa) 76%,
      #ffffffcc 100%
    ),
    linear-gradient(
      0deg,
      color-mix(in srgb, var(--text) 15%, transparent),
      transparent 45%
    );
  pointer-events: none;
}

.card-art :deep(.portrait) {
  width: 100%;
  height: 100%;
  border-radius: 0;
  background: transparent;
}

.card-art :deep(img) {
  transition: scale 0.35s ease;
}

.character-card:hover .card-art :deep(img),
.character-card:focus-visible .card-art :deep(img) {
  scale: 1.025;
}

.card-content {
  position: absolute;
  inset: 0 0 0 45%;
  z-index: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
  padding: 16px 24px 16px clamp(20px, 2vw, 32px);
  background: linear-gradient(90deg, #fff0, #ffffff1a 26%, #ffffff3d);
  backdrop-filter: blur(1px);
  color: var(--text);
}

.current-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  margin-bottom: 9px;
  border-radius: 99px;
  background: linear-gradient(125deg, var(--primary), var(--accent));
  color: white;
  font-size: 11px;
}

.card-heart {
  position: absolute;
  top: 24px;
  right: 26px;
  color: color-mix(in srgb, var(--accent) 80%, white);
  opacity: 0.8;
  transform: rotate(-10deg);
}

.romanized {
  color: color-mix(in srgb, var(--text) 68%, var(--muted));
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 4px;
  text-transform: uppercase;
}

.card-content h2 {
  margin: 7px 0 7px;
  color: var(--text);
  font-size: clamp(24px, 2vw, 31px);
  letter-spacing: 2px;
  writing-mode: horizontal-tb;
}

.tagline {
  display: -webkit-box;
  max-width: 36ch;
  margin: 0;
  overflow: hidden;
  color: color-mix(in srgb, var(--text) 72%, var(--muted));
  font-family: "Kaiti SC", "STKaiti", "KaiTi", serif;
  font-size: 14px;
  line-height: 1.65;
  letter-spacing: 0.02em;
  transform: rotate(-1.2deg);
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 10px;
}

.tag-list span {
  padding: 5px 10px;
  border-radius: 99px;
  background: #ffffff8a;
  color: var(--muted);
  font-size: 10px;
}

.visit-action {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: auto;
  margin-top: 11px;
  padding: 8px 3px;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--accent);
  font-size: 13px;
  font-weight: 700;
}

.character-panel.character-card.featured {
  background: color-mix(in srgb, var(--secondary) 42%, white);
}

.featured .card-content {
  inset: 0 0 0 57%;
  padding: 20px clamp(24px, 3vw, 46px) 20px clamp(20px, 2.6vw, 36px);
  background: linear-gradient(90deg, #fff0, #ffffff15 22%, #ffffff40 100%);
  backdrop-filter: blur(1.5px);
}

.featured .tagline {
  font-family: "Kaiti SC", "STKaiti", "KaiTi", serif;
  max-width: 26ch;
  color: color-mix(in srgb, var(--accent) 74%, var(--text));
  font-size: 18px;
  line-height: 1.65;
  transform: rotate(-2.2deg);
}

.featured .visit-action {
  margin-top: 15px;
  padding: 10px 18px;
  border: 1px solid color-mix(in srgb, var(--accent) 20%, transparent);
  border-radius: 99px;
  background: linear-gradient(125deg, var(--primary), var(--accent));
  box-shadow: 0 8px 18px color-mix(in srgb, var(--accent) 20%, transparent);
  color: white;
}

@media (max-width: 1100px) {
  .card-content {
    left: 42%;
    padding-left: 20px;
  }

  .featured .card-content {
    left: 54%;
  }

  .character-panel.character-card.featured {
    min-height: 240px;
  }
}

@media (max-width: 700px) {
  .card-art::after {
    background: linear-gradient(0deg, var(--card-tint), transparent 60%);
  }

  .card-content,
  .featured .card-content {
    inset: auto 0 0;
    min-height: 48%;
    padding: 20px 22px 22px;
    background: linear-gradient(0deg, #ffffffc9, #ffffff4f 72%, transparent);
  }
}
</style>
