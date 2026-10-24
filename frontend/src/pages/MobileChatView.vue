<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, type CSSProperties } from "vue";
import { ArrowLeft, MoreHorizontal } from "lucide-vue-next";
import { useAfterStory } from "../composables/useAfterStory";
import { returnFromChat } from "../composables/mobileChatNavigation";
import CharacterAvatar from "../components/CharacterAvatar.vue";
import ChatConversation from "./ChatConversation.vue";
import "./mobile-chat.css";

const mobileScenes: Record<string, string> = {
  nanally: "/mobile-scenes/nanally.webp",
  iroi: "/mobile-scenes/iroi.webp",
  mint: "/mobile-scenes/mint.webp",
};
const { character, chat, cover, connected, editing, scrollArea, route } =
  useAfterStory();
const sceneSource = computed(() => {
  const current = character.value;
  if (!current) return "";
  const selectedCover = cover(current).source;
  if (selectedCover && selectedCover !== current.cover) return selectedCover;
  return mobileScenes[current.id] || current.sceneBackground || selectedCover;
});
const menuOpen = ref(false);
const viewportHeight = ref<number>();
const viewportTop = ref(0);
const keyboardOpen = ref(false);
const viewportStyle = computed<CSSProperties>(
  () =>
    ({
      "--chat-viewport-height": viewportHeight.value
        ? `${viewportHeight.value}px`
        : undefined,
      "--chat-viewport-top": `${viewportTop.value}px`,
      "--chat-safe-bottom": keyboardOpen.value ? "0px" : undefined,
    }) as CSSProperties,
);
const presence = computed(() => {
  if (!connected.value) return "稍等片刻";
  if (chat.value?.sending) return "正在想怎么和你说…";
  if (chat.value?.loading) return "正在翻开我们的对话…";
  return "在这里";
});

function updateViewport() {
  const area = scrollArea.value;
  const nearBottom =
    !!area && area.scrollHeight - area.clientHeight - area.scrollTop <= 56;
  const previousTop = area?.scrollTop || 0;
  const viewport = window.visualViewport;
  viewportHeight.value = viewport?.height || window.innerHeight;
  viewportTop.value = viewport?.offsetTop || 0;
  keyboardOpen.value =
    !!viewport &&
    window.innerHeight - viewport.height - viewport.offsetTop > 120;
  requestAnimationFrame(() => {
    if (!area || area !== scrollArea.value) return;
    area.scrollTop = nearBottom ? area.scrollHeight : previousTop;
  });
}
function selectDestination(destination: "profile" | "history" | "edit") {
  menuOpen.value = false;
  if (destination === "edit") editing.value = true;
  else route(destination);
}
function closeMenu(event: KeyboardEvent) {
  if (event.key === "Escape") menuOpen.value = false;
}
onMounted(() => {
  updateViewport();
  window.visualViewport?.addEventListener("resize", updateViewport);
  window.visualViewport?.addEventListener("scroll", updateViewport);
  window.addEventListener("resize", updateViewport);
  window.addEventListener("keydown", closeMenu);
});
onUnmounted(() => {
  window.visualViewport?.removeEventListener("resize", updateViewport);
  window.visualViewport?.removeEventListener("scroll", updateViewport);
  window.removeEventListener("resize", updateViewport);
  window.removeEventListener("keydown", closeMenu);
});
</script>

<template>
  <main
    v-if="character"
    id="main-content"
    tabindex="-1"
    class="chat-workspace mobile-chat-workspace"
    :style="viewportStyle"
    :data-version="chat?.session?.version_id"
  >
    <img
      v-if="sceneSource"
      class="mobile-scene-background"
      :src="sceneSource"
      alt=""
      aria-hidden="true"
    />
    <section class="chat-glass">
      <header class="chat-header">
        <button
          class="mobile-chat-back"
          type="button"
          aria-label="返回上一页"
          @click="returnFromChat(route)"
        >
          <ArrowLeft :size="23" aria-hidden="true" />
        </button>
        <CharacterAvatar :character="character" :cover="cover(character)" />
        <div class="chat-identity">
          <h2>{{ character.name }}</h2>
          <span class="presence-status"
            ><i :class="{ online: connected }"></i>{{ presence }}</span
          >
        </div>
        <button
          class="mobile-chat-more"
          type="button"
          aria-label="更多聊天操作"
          :aria-expanded="menuOpen"
          aria-controls="mobile-chat-menu"
          @click="menuOpen = !menuOpen"
        >
          <MoreHorizontal :size="23" aria-hidden="true" />
        </button>
      </header>
      <template v-if="menuOpen">
        <button
          class="mobile-chat-menu-backdrop"
          type="button"
          aria-label="关闭更多操作"
          @click="menuOpen = false"
        ></button>
        <div
          id="mobile-chat-menu"
          class="mobile-chat-menu"
          role="group"
          aria-label="聊天操作"
        >
          <button type="button" @click="selectDestination('profile')">
            角色资料
          </button>
          <button type="button" @click="selectDestination('history')">
            查看回忆
          </button>
          <button type="button" @click="selectDestination('edit')">
            调整场景
          </button>
        </div>
      </template>
      <ChatConversation :character="character" mobile />
    </section>
  </main>
</template>
