<script setup lang="ts">
import { computed } from "vue";
import { Heart } from "lucide-vue-next";
import { useAfterStory } from "../composables/useAfterStory";
import CharacterCard from "../components/CharacterCard.vue";

const { character, characters, selected, cover, choose } = useAfterStory();

const others = computed(() =>
  characters.value.filter((item) => item.id !== selected.value),
);
</script>

<template>
  <main v-if="character" id="main-content" tabindex="-1" class="selection-page">
    <header class="characters-heading">
      <div>
        <small>ACROSS WORLDS</small>
        <h1>今天，想和谁说说话？<Heart :size="35" /></h1>
        <p>每一个角色，都在自己的故事里等你。</p>
      </div>
      <span>选择今天想靠近的那一个。<br />♡</span>
    </header>

    <section class="characters-stage" aria-label="选择今天想相见的角色">
      <section class="current-character" aria-label="当前陪伴角色">
        <CharacterCard
          :character="character"
          :cover="cover(character)"
          current
          featured
          @select="choose(character)"
        />
      </section>

      <aside
        v-if="others.length"
        class="other-characters"
        aria-label="也可以去见"
      >
        <div class="other-characters-heading">
          <span>ALSO WAITING</span>
          <p>也有两段故事，正在等你推开门。</p>
        </div>
        <CharacterCard
          v-for="item in others"
          :key="item.id"
          :character="item"
          :cover="cover(item)"
          @select="choose(item)"
        />
      </aside>
    </section>

    <footer class="characters-footer">
      <span>每一次相遇，都是新的故事。</span>
      <span>不同的世界，同一份心动。 ♡</span>
    </footer>
  </main>
</template>

<style scoped>
.selection-page {
  box-sizing: border-box;
  width: 100%;
  max-width: 1500px;
  margin: 0 auto;
}

.characters-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 0;
  padding: 0 clamp(2px, 1vw, 14px);
}

.characters-heading small {
  color: var(--muted);
  font-size: 9px;
  letter-spacing: 4px;
}

.characters-heading h1 {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 5px 0 4px;
  color: var(--text);
  font-size: clamp(32px, 2.6vw, 42px);
  letter-spacing: -1px;
}

.characters-heading h1 svg {
  flex-shrink: 0;
  color: var(--accent);
  transform: rotate(-13deg);
}

.characters-heading p,
.characters-heading > span {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.5;
}

.characters-heading > span {
  padding-bottom: 2px;
  color: var(--accent);
  text-align: right;
  transform: rotate(-3deg);
}

.characters-stage {
  display: grid;
  grid-template-columns: minmax(0, 1.58fr) minmax(350px, 0.92fr);
  gap: 20px;
  min-height: 0;
}

.current-character {
  min-width: 0;
  min-height: 0;
}
.other-characters {
  display: grid;
  grid-template-rows: auto repeat(2, minmax(0, 1fr));
  gap: 10px;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  padding: 0 2px 0 0;
  align-content: stretch;
}

.other-characters-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  min-height: 17px;
  padding: 0 5px;
}

.other-characters-heading span {
  color: var(--muted);
  font-size: 9px;
  letter-spacing: 0.22em;
}

.other-characters-heading p {
  margin: 0;
  color: var(--muted);
  font-family: "Kaiti SC", "STKaiti", "KaiTi", serif;
  font-size: 12px;
  opacity: 0.8;
  text-align: right;
  transform: rotate(-1.5deg);
}

.characters-footer {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  margin-top: 0;
  padding: 0 8px;
  color: var(--muted);
  font-size: 11px;
}

@media (min-width: 761px) {
  .selection-page {
    height: calc(100dvh - var(--desktop-header-height));
    padding-block: var(--page-padding-y);
    display: grid;
    grid-template-rows: auto minmax(0, 1fr) auto;
    gap: var(--page-gap);
  }
}

@media (min-width: 1700px) {
  .selection-page {
    max-width: 1640px;
  }
}

@media (max-width: 1100px) {
  .characters-stage {
    grid-template-columns: minmax(0, 1.35fr) minmax(315px, 0.9fr);
  }
}

@media (min-width: 761px) and (max-height: 800px) {
  .characters-heading h1 {
    margin: 6px 0 4px;
    font-size: 32px;
  }

  .characters-heading p,
  .characters-heading > span {
    font-size: 12px;
  }

  .other-characters-heading p {
    font-size: 11px;
  }
}

@media (max-width: 900px) {
  .selection-page {
    margin-top: 18px;
  }

  .characters-stage {
    grid-template-columns: 1fr;
  }

  .other-characters {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    grid-template-rows: auto minmax(0, 1fr);
  }

  .other-characters-heading {
    grid-column: 1 / -1;
  }

  .characters-heading {
    align-items: flex-start;
  }

  .characters-heading > span {
    display: none;
  }
}

@media (max-width: 600px) {
  .characters-heading h1 {
    font-size: 29px;
  }

  .characters-heading h1 svg {
    display: none;
  }

  .characters-footer {
    flex-wrap: wrap;
  }
}
</style>
