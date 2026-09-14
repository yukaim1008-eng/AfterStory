<script setup lang="ts">
import { Home, UsersRound, History, Settings } from "lucide-vue-next";
defineProps<{ page: string }>();
const emit = defineEmits<{ navigate: [page: string] }>();
const links = [
  { page: "home", label: "首页", icon: Home },
  { page: "characters", label: "角色", icon: UsersRound },
  { page: "history", label: "回忆", icon: History },
  { page: "settings", label: "设置", icon: Settings },
];
</script>
<template>
  <header class="topbar" :class="{ 'topbar-quiet': page === 'chat' }">
    <a class="brand" href="#/home" @click.prevent="emit('navigate', 'home')"
      >AfterStory<span></span
    ></a>
    <div class="topbar-line"></div>
    <span class="tagline">故事之外，与你相见。</span>
    <nav aria-label="主导航">
      <button
        v-for="link in links"
        :key="link.page"
        :class="{
          active:
            page === link.page ||
            (link.page === 'history' && page === 'memory') ||
            (link.page === 'characters' && page === 'profile'),
        }"
        :aria-current="
          page === link.page || (link.page === 'history' && page === 'memory')
            ? 'page'
            : undefined
        "
        @click="emit('navigate', link.page)"
      >
        <component :is="link.icon" :size="19" /><span>{{ link.label }}</span>
      </button>
    </nav>
  </header>
</template>
