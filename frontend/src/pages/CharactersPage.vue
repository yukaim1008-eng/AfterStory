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
        <p>在这里，总有一个特别的她，正等着与你相遇。</p>
      </div>
      <span>不同的世界，<br />同一份期待。 ♡</span>
    </header>

    <section class="current-character" aria-label="当前角色">
      <CharacterCard
        :character="character"
        :cover="cover(character)"
        current
        featured
        @select="choose(character)"
      />
    </section>

    <section
      v-if="others.length"
      class="other-characters"
      aria-label="其他角色"
    >
      <CharacterCard
        v-for="item in others"
        :key="item.id"
        :character="item"
        :cover="cover(item)"
        @select="choose(item)"
      />
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
  margin: clamp(20px, 3vh, 42px) auto 0;
}

.characters-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 32px;
  margin-bottom: 26px;
  padding: 0 clamp(2px, 1vw, 14px);
}

.characters-heading small {
  color: var(--muted);
  font-size: 10px;
  letter-spacing: 5px;
}

.characters-heading h1 {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 11px 0 8px;
  color: var(--text);
  font-size: clamp(30px, 3vw, 48px);
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
  line-height: 1.8;
}

.characters-heading > span {
  padding-bottom: 7px;
  color: var(--accent);
  text-align: right;
  transform: rotate(-3deg);
}

.current-character {
  width: 100%;
}

.other-characters {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  width: 100%;
  margin-top: 18px;
}

.characters-footer {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  margin-top: 24px;
  padding: 0 8px;
  color: var(--muted);
  font-size: 11px;
}

@media (min-width: 1700px) {
  .selection-page {
    max-width: 1640px;
  }
}

@media (max-width: 1100px) {
  .other-characters {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .selection-page {
    margin-top: 18px;
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
