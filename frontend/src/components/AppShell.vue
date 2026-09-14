<script setup lang="ts">
import { computed } from "vue";
import type { Character } from "../types";
import { themeStyle } from "../theme";
import TopNavigation from "./TopNavigation.vue";
import PageBackground from "./PageBackground.vue";
const props = defineProps<{
  character?: Character;
  source?: string;
  page: string;
  motion: boolean;
  font: string;
}>();
const emit = defineEmits<{ navigate: [page: string] }>();
const theme = computed(() => themeStyle(props.character));
</script>
<template>
  <div
    class="application"
    :style="theme"
    :class="[{ 'reduce-motion': !motion }, `font-${font}`, `page-${page}`]"
  >
    <PageBackground :source="source" />
    <a
      class="skip-link"
      href="#main-content"
      @click.prevent="($el.querySelector('main') as HTMLElement)?.focus()"
      >跳到主要内容</a
    >
    <TopNavigation :page="page" @navigate="emit('navigate', $event)" />
    <slot />
  </div>
</template>
