<script setup lang="ts">
import { computed, watch } from "vue";
import type { Character } from "../types";
import { themeStyle } from "../theme";
import { rememberChatOrigin } from "../composables/mobileChatNavigation";
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
watch(
  () => props.page,
  (next, previous) => rememberChatOrigin(next, previous),
  { immediate: true },
);
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
    <TopNavigation
      v-if="page !== 'chat'"
      :page="page"
      mobile
      @navigate="emit('navigate', $event)"
    />
  </div>
</template>
