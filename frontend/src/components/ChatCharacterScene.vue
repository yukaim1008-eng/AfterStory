<script setup lang="ts">
import { ImagePlus } from "lucide-vue-next";
import Portrait from "../Portrait.vue";
import { useAfterStory } from "../composables/useAfterStory";

const { character, cover, connected, editing } = useAfterStory();
</script>

<template>
  <aside
    v-if="character"
    class="chat-character-scene"
    :aria-label="`${character.name}的角色场景`"
  >
    <div class="scene-backdrop" aria-hidden="true">
      <Portrait
        :source="cover(character).source"
        :crop="cover(character).crop.chat"
        :name="character.name"
      />
    </div>
    <div class="scene-portrait" aria-hidden="true">
      <Portrait
        :source="cover(character).source"
        :crop="cover(character).crop.chat"
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
.scene-portrait :deep(.portrait) {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.scene-backdrop {
  inset: -4%;
  opacity: 0.5;
}

.scene-backdrop :deep(img) {
  object-fit: cover;
  filter: blur(10px) saturate(0.9) brightness(1.08);
  transform: scale(1.08) !important;
}

.scene-portrait {
  right: auto;
  width: min(82%, 1180px);
  mask-image: linear-gradient(90deg, #000 0 62%, #000d 74%, transparent 96%);
  -webkit-mask-image: linear-gradient(
    90deg,
    #000 0 62%,
    #000d 74%,
    transparent 96%
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

.scene-color,
.scene-light,
.scene-vignette {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.scene-color {
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
  inset: -15% 30% 20% -15%;
  border-radius: 50%;
  background: #fff7;
  filter: blur(48px);
  mix-blend-mode: soft-light;
}

.scene-vignette {
  background:
    radial-gradient(circle at 28% 27%, transparent 0 24%, #2b172316 67%),
    linear-gradient(0deg, #181019a8, transparent 39%);
}

.scene-identity {
  position: absolute;
  z-index: 2;
  bottom: clamp(30px, 5vh, 58px);
  left: clamp(28px, 4vw, 64px);
  width: min(35vw, 430px);
  color: #fff;
  text-shadow: 0 2px 20px #1d111c70;
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
    width: 88%;
  }

  .scene-identity {
    width: 31vw;
  }
}

@media (max-width: 700px) {
  .scene-portrait {
    width: 100%;
    opacity: 0.78;
    mask-image: linear-gradient(180deg, #000 0 42%, transparent 82%);
    -webkit-mask-image: linear-gradient(180deg, #000 0 42%, transparent 82%);
  }

  .scene-identity {
    display: none;
  }
}
</style>
