<script setup lang="ts">
import { computed, type Component, type CSSProperties } from "vue";
import { Heart, ImagePlus, Images, Sparkles } from "lucide-vue-next";
import Portrait from "../Portrait.vue";
import { useAfterStory } from "../composables/useAfterStory";
import {
  formatSceneDecorationText,
  resolveSceneDecorations,
} from "../sceneDecorations";
import type { SceneDecorationNote, SceneSpaceEntry } from "../types";

const { character, cover, connected, editing, route } = useAfterStory();
const sceneSource = computed(() => {
  if (!character.value) return "";
  return character.value.sceneBackground || cover(character.value).source;
});
const sceneCrop = computed(() => {
  if (!character.value) return { x: 50, y: 50, zoom: 1 };
  return character.value.sceneBackground
    ? { x: 50, y: 50, zoom: 1 }
    : cover(character.value).crop.chat;
});
const scenePosition = computed(() => character.value?.sceneBackgroundPosition);
const decorations = computed(() =>
  character.value ? resolveSceneDecorations(character.value) : undefined,
);
const entryIcons: Record<SceneSpaceEntry["icon"], Component> = {
  Images,
  Heart,
  Sparkles,
};

function openSpaceEntry(entry: SceneSpaceEntry) {
  if (entry.action === "album") editing.value = true;
  else route(entry.action);
}

function decorationText(text: string) {
  return character.value
    ? formatSceneDecorationText(text, character.value)
    : text;
}

function entryStyle(entry: SceneSpaceEntry): CSSProperties {
  return {
    "--entry-offset": `${entry.offsetX || 0}px`,
    "--divider-width": `${entry.dividerWidth || 76}%`,
  } as CSSProperties;
}

function sceneSpaceStyle(): CSSProperties {
  return {
    "--scene-space-color":
      decorations.value?.spaceColor || "rgba(255, 255, 255, 0.84)",
  } as CSSProperties;
}

function signatureStyle(note?: SceneDecorationNote & { indent?: number }) {
  if (!note) return undefined;
  return {
    marginLeft: `${note.indent || 0}px`,
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
  <aside
    v-if="character"
    class="chat-character-scene"
    :aria-label="`${character.name}的角色场景`"
  >
    <div class="scene-backdrop" aria-hidden="true">
      <Portrait
        :source="sceneSource"
        :crop="sceneCrop"
        :position="scenePosition"
        :name="character.name"
      />
    </div>
    <div class="scene-portrait" aria-hidden="true">
      <Portrait
        :source="sceneSource"
        :crop="sceneCrop"
        :position="scenePosition"
        :name="character.name"
      />
    </div>
    <div class="scene-interlock" aria-hidden="true">
      <Portrait
        :source="sceneSource"
        :crop="sceneCrop"
        :position="scenePosition"
        :name="character.name"
      />
    </div>
    <div class="scene-color" aria-hidden="true"></div>
    <div class="scene-light" aria-hidden="true"></div>
    <div class="scene-vignette" aria-hidden="true"></div>

    <div class="scene-identity">
      <small>{{ character.world }} · {{ character.romanized }}</small>
      <h1>{{ character.name }}</h1>
      <p>{{ character.tagline || character.description }}</p>
      <button
        class="scene-cover-action"
        aria-label="更换封面"
        :disabled="!connected"
        @click="editing = true"
      >
        <ImagePlus :size="15" />调整场景
      </button>
    </div>

    <div
      v-if="decorations"
      :key="character.id"
      class="scene-space decoration-enter"
      :style="sceneSpaceStyle()"
    >
      <nav aria-label="角色空间入口">
        <button
          v-for="entry in decorations.leftMenu"
          :key="`${entry.action}-${entry.text}`"
          type="button"
          :class="`icon-${entry.iconPosition || 'start'}`"
          :style="entryStyle(entry)"
          @click="openSpaceEntry(entry)"
        >
          <component
            :is="entryIcons[entry.icon]"
            class="entry-icon"
            :size="17"
          />
          <span>{{ decorationText(entry.text) }}</span>
        </button>
      </nav>
      <p
        v-if="decorations.signature"
        class="scene-signature"
        :style="signatureStyle(decorations.signature)"
      >
        {{ decorationText(decorations.signature.text) }}
      </p>
    </div>
  </aside>
</template>

<style scoped>
.chat-character-scene {
  position: absolute;
  inset: 0;
  overflow: hidden;
  background: linear-gradient(
    118deg,
    color-mix(in srgb, var(--secondary) 74%, #fff) 0%,
    color-mix(in srgb, var(--background) 76%, var(--soft)) 56%,
    color-mix(in srgb, var(--soft) 58%, #fff) 100%
  );
}

.scene-backdrop,
.scene-backdrop :deep(.portrait),
.scene-portrait,
.scene-portrait :deep(.portrait),
.scene-interlock,
.scene-interlock :deep(.portrait) {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.scene-backdrop {
  z-index: 0;
  inset: -4%;
  opacity: 0.54;
}

.scene-backdrop :deep(img) {
  object-fit: cover;
  filter: blur(10px) saturate(0.9) brightness(1.08);
  transform: scale(1.08) !important;
}

.scene-portrait {
  z-index: 2;
  right: auto;
  width: min(90%, 1420px);
  mask-image: linear-gradient(90deg, #000 0 64%, #000e 76%, transparent 100%);
  -webkit-mask-image: linear-gradient(
    90deg,
    #000 0 64%,
    #000e 76%,
    transparent 100%
  );
}

.scene-portrait :deep(.portrait) {
  background: transparent;
}

.scene-portrait :deep(img) {
  object-fit: cover;
  filter: saturate(1.04) contrast(1.02);
  transform: scale(1.02) !important;
}

.scene-interlock {
  z-index: 5;
  right: auto;
  width: min(90%, 1420px);
  pointer-events: none;
  opacity: 0.94;
  mask-image: linear-gradient(
    90deg,
    transparent 0 42%,
    #000 47% 55%,
    transparent 64% 100%
  );
  -webkit-mask-image: linear-gradient(
    90deg,
    transparent 0 42%,
    #000 47% 55%,
    transparent 64% 100%
  );
}

.scene-interlock :deep(.portrait) {
  background: transparent;
}

.scene-interlock :deep(img) {
  object-fit: cover;
  filter: saturate(1.04) contrast(1.02);
  transform: scale(1.02) !important;
}

.scene-color,
.scene-light,
.scene-vignette {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.scene-color {
  z-index: 1;
  background:
    linear-gradient(
      90deg,
      color-mix(in srgb, var(--primary) 8%, transparent),
      transparent 38%,
      color-mix(in srgb, var(--background) 34%, transparent) 66%,
      color-mix(in srgb, var(--background) 72%, transparent)
    ),
    linear-gradient(180deg, #fff2 0%, transparent 38%, #16101c70 100%);
}

.scene-light {
  z-index: 3;
  inset: -15% 30% 20% -15%;
  border-radius: 50%;
  background: #fff7;
  filter: blur(48px);
  mix-blend-mode: soft-light;
}

.scene-vignette {
  z-index: 3;
  background:
    radial-gradient(circle at 28% 27%, transparent 0 24%, #2b172316 67%),
    linear-gradient(0deg, #181019a8, transparent 39%);
}

.scene-identity {
  position: absolute;
  z-index: 4;
  bottom: clamp(236px, 31vh, 326px);
  left: clamp(28px, 4vw, 64px);
  width: min(35vw, 430px);
  color: #fff;
  text-shadow: 0 2px 20px #1d111c70;
}

.scene-space {
  position: absolute;
  z-index: 6;
  bottom: clamp(26px, 4vh, 46px);
  left: clamp(28px, 4vw, 64px);
  width: clamp(190px, 16vw, 226px);
  color: #fff;
  text-shadow: 0 2px 18px rgba(29, 17, 28, 0.32);
}

.scene-space nav {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.scene-space button {
  position: relative;
  min-height: 37px;
  gap: 10px;
  padding: 6px 7px 10px;
  border-radius: 0;
  background: transparent;
  color: var(--scene-space-color);
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 0.035em;
  text-shadow: 0 2px 14px rgba(29, 17, 28, 0.28);
  transform: translateX(var(--entry-offset));
  transition:
    color 190ms ease,
    transform 190ms ease;
}

.scene-space button::after {
  position: absolute;
  bottom: 3px;
  left: 4px;
  width: var(--divider-width);
  height: 1px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.56), transparent);
  content: "";
  opacity: 0.72;
  transition:
    width 190ms ease,
    opacity 190ms ease;
}

.scene-space button.icon-end {
  justify-content: space-between;
}

.scene-space button.icon-end .entry-icon {
  order: 2;
}

.scene-space button.icon-end::after {
  right: 4px;
  left: auto;
  background: linear-gradient(270deg, rgba(255, 255, 255, 0.56), transparent);
}

.scene-space button .entry-icon {
  flex: 0 0 auto;
  color: color-mix(in srgb, var(--scene-space-color) 86%, transparent);
  filter: drop-shadow(0 1px 5px rgba(29, 17, 28, 0.22));
}

.scene-space button:hover:not(:disabled) {
  background: transparent;
  color: color-mix(in srgb, var(--scene-space-color) 88%, white);
  transform: translateX(calc(var(--entry-offset) + 2px));
}

.scene-space button:hover:not(:disabled)::after {
  width: calc(var(--divider-width) + 4%);
  opacity: 1;
}

.scene-signature {
  width: max-content;
  max-width: calc(100% - 16px);
  margin-top: 30px;
  margin-bottom: 0;
  color: rgba(255, 255, 255, 0.8);
  font-size: clamp(17px, 1.3vw, 19px);
  font-weight: 400;
  line-height: 1.7;
  letter-spacing: 0.08em;
  transform-origin: left center;
  text-wrap: balance;
  white-space: pre-line;
}

.decoration-enter {
  animation: decoration-enter 220ms ease-out both;
}

@keyframes decoration-enter {
  from {
    filter: opacity(0);
    translate: 0 3px;
  }
  to {
    filter: opacity(1);
    translate: 0 0;
  }
}

.scene-identity small {
  color: #ffffffd1;
  font-size: var(--type-eyebrow-size);
  font-weight: 600;
  letter-spacing: var(--type-eyebrow-tracking);
}

.scene-identity h1 {
  margin: 9px 0 11px;
  color: #fff;
  font-size: var(--type-character-size);
  font-weight: 650;
  line-height: 1.08;
  letter-spacing: 0.08em;
}

.scene-identity p {
  max-width: 28ch;
  margin: 0;
  color: #ffffffe8;
  font-size: var(--type-handwriting-size);
  font-style: italic;
  font-weight: var(--type-handwriting-weight);
  line-height: 1.75;
  letter-spacing: var(--type-handwriting-tracking);
}

.scene-cover-action {
  margin-top: 15px;
  padding: 8px 0;
  border-radius: 0;
  color: #ffffffcf;
  font-size: 11px;
  letter-spacing: 0.05em;
  text-shadow: inherit;
}

.scene-cover-action:hover:not(:disabled) {
  background: transparent;
  color: #fff;
}

@media (max-width: 1050px) {
  .scene-portrait {
    width: 100%;
  }

  .scene-interlock {
    width: 100%;
    mask-image: linear-gradient(
      90deg,
      transparent 0 34%,
      #000 41% 57%,
      transparent 69% 100%
    );
    -webkit-mask-image: linear-gradient(
      90deg,
      transparent 0 34%,
      #000 41% 57%,
      transparent 69% 100%
    );
  }

  .scene-identity {
    width: 31vw;
  }

  .scene-space {
    width: 210px;
  }
}

@media (max-height: 760px) and (min-width: 701px) {
  .scene-identity {
    bottom: 218px;
  }

  .scene-identity p,
  .scene-cover-action {
    display: none;
  }

  .scene-space {
    bottom: 22px;
  }

  .scene-signature {
    margin-top: 18px;
  }
}

@media (max-width: 700px) {
  .scene-portrait {
    width: 100%;
    opacity: 0.78;
    mask-image: linear-gradient(180deg, #000 0 42%, transparent 82%);
    -webkit-mask-image: linear-gradient(180deg, #000 0 42%, transparent 82%);
  }

  .scene-interlock {
    display: none;
  }

  .scene-identity {
    display: none;
  }

  .scene-space {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .decoration-enter {
    animation: none;
  }
}
</style>
