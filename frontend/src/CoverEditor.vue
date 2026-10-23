<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { X, Upload, Check } from "lucide-vue-next";
import Portrait from "./Portrait.vue";
import type { Character, Cover } from "./types";
const props = defineProps<{ character: Character; value: Cover }>();
const emit = defineEmits<{ close: []; save: [value: Cover] }>();
const draft = ref<Cover>(JSON.parse(JSON.stringify(props.value)));
const target = ref<"chat" | "selection">("chat");
const error = ref("");
const confirmDiscard = ref(false);
const closeButton = ref<HTMLButtonElement | null>(null);
let previousFocus: HTMLElement | null = null;
let previousBodyOverflow = "";
onMounted(() => {
  previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  previousBodyOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
  closeButton.value?.focus();
});
onUnmounted(() => {
  document.body.style.overflow = previousBodyOverflow;
  previousFocus?.focus();
});
function requestClose() {
  const unchanged = JSON.stringify(draft.value) === JSON.stringify(props.value);
  if (unchanged || !window.matchMedia("(max-width: 760px), (pointer: coarse) and (max-height: 500px) and (max-width: 1023px)").matches) {
    emit("close");
  } else {
    confirmDiscard.value = true;
  }
}
async function upload(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (!file) return;
  if (
    !["image/jpeg", "image/png", "image/webp"].includes(file.type) ||
    file.size > 10 * 1024 * 1024
  ) {
    error.value = "请选择 10 MB 以内的 JPG、PNG 或 WebP 图片。";
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    const img = new Image();
    img.onload = () => {
      draft.value.source = String(reader.result);
      error.value = "";
    };
    img.onerror = () => {
      error.value = "无法读取这张图片，请换一张。";
    };
    img.src = String(reader.result);
  };
  reader.onerror = () => {
    error.value = "图片读取失败，请重试。";
  };
  reader.readAsDataURL(file);
}
</script>
<template>
  <div
    class="modal-shade"
    @click.self="requestClose"
    @keydown.esc.stop.prevent="requestClose"
  >
    <section
      class="modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cover-title"
    >
      <header>
        <div>
          <small>APPEARANCE</small>
          <h2 id="cover-title">让她以你喜欢的样子出现</h2>
        </div>
        <button ref="closeButton" aria-label="关闭" @click="requestClose">
          <X :size="20" />
        </button>
      </header>
      <p class="muted">
        仅保存到当前浏览器的当前用户 · {{ character.name }}，不修改角色资料。
      </p>
      <div class="cover-previews">
        <div :class="{ 'active-mobile-preview': target === 'chat' }">
          <Portrait
            :source="draft.source"
            :crop="draft.crop.chat"
            :name="character.name"
          /><small>聊天封面</small>
        </div>
        <div :class="{ 'active-mobile-preview': target === 'selection' }">
          <Portrait
            :source="draft.source"
            :crop="draft.crop.selection"
            :name="character.name"
          /><small>选择页 · 展开</small>
        </div>
        <div class="narrow-preview">
          <Portrait
            :source="draft.source"
            :crop="draft.crop.selection"
            :name="character.name"
          /><small>收起</small>
        </div>
      </div>
      <div class="segmented">
        <button
          v-for="(label, key) in { chat: '聊天封面', selection: '角色选择' }"
          :key="key"
          :class="{ active: target === key }"
          @click="target = key"
        >
          {{ label }}
        </button>
      </div>
      <div class="sliders">
        <label
          >左右位置<input
            v-model.number="draft.crop[target].x"
            type="range"
            min="0"
            max="100" /></label
        ><label
          >上下位置<input
            v-model.number="draft.crop[target].y"
            type="range"
            min="0"
            max="100" /></label
        ><label
          >放大<input
            v-model.number="draft.crop[target].zoom"
            type="range"
            min="1"
            max="3"
            step="0.01"
        /></label>
      </div>
      <p v-if="error" role="alert" class="error">{{ error }}</p>
      <div v-if="confirmDiscard" class="discard-confirm" role="alertdialog" aria-label="放弃封面修改">
        <p>尚未保存的封面调整会丢失。</p>
        <button @click="confirmDiscard = false">继续编辑</button>
        <button @click="emit('close')">放弃修改</button>
      </div>
      <footer>
        <label class="text-action upload"
          ><Upload :size="17" />选择图片<input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            @change="upload" /></label
        ><button @click="requestClose">取消</button
        ><button class="primary" @click="emit('save', draft)">
          <Check :size="16" />保存封面
        </button>
      </footer>
    </section>
  </div>
</template>
<style scoped>
.discard-confirm { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 12px; padding: 12px; border: 1px solid var(--soft); border-radius: 12px; background: #fff5f8; }
.discard-confirm p { flex: 1 1 100%; margin: 0; color: var(--text); font-size: 13px; }
.discard-confirm button { min-height: 44px; padding: 8px 12px; }
.discard-confirm button:last-child { color: #a73354; }
@media (max-width: 760px),
  (pointer: coarse) and (max-height: 500px) and (max-width: 1023px) {
  .modal-shade {
    align-items: stretch;
    padding: max(8px, env(safe-area-inset-top)) 8px max(8px, env(safe-area-inset-bottom));
    backdrop-filter: none;
  }
  .modal {
    box-sizing: border-box;
    width: 100%;
    max-width: none;
    max-height: 100%;
    padding: 16px;
    overflow-x: hidden;
    overflow-y: auto;
    overscroll-behavior: contain;
  }
  .modal header { gap: 8px; }
  .modal header > button { flex: none; min-width: 44px; min-height: 44px; }
  .modal h2 { margin: 4px 0 10px; font-size: 20px; line-height: 1.35; }
  .cover-previews {
    justify-content: center;
    height: clamp(190px, 34vh, 290px);
    margin: 14px 0 20px;
  }
  .cover-previews > div { display: none; flex: none; width: min(100%, 270px); }
  .cover-previews > .active-mobile-preview { display: block; }
  .segmented { display: grid; grid-template-columns: 1fr 1fr; width: 100%; box-sizing: border-box; }
  .segmented button { min-height: 44px; }
  .sliders { flex-direction: column; gap: 4px; margin-top: 16px; }
  .sliders label { display: block; min-height: 48px; }
  .sliders input { min-height: 32px; margin: 4px 0; }
  .modal footer { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; }
  .modal footer > * { min-height: 44px; justify-content: center; }
  .modal footer .upload { grid-column: 1 / -1; width: 100%; margin: 0; padding: 8px; border: 1px solid var(--soft); border-radius: 10px; box-sizing: border-box; }
}
</style>
