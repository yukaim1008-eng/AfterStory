<script setup lang="ts">
import { ref } from "vue";
import { X, Upload, Check } from "lucide-vue-next";
import Portrait from "./Portrait.vue";
import type { Character, Cover } from "./types";
const props = defineProps<{ character: Character; value: Cover }>();
const emit = defineEmits<{ close: []; save: [value: Cover] }>();
const draft = ref<Cover>(JSON.parse(JSON.stringify(props.value)));
const target = ref<"chat" | "selection">("chat");
const error = ref("");
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
    @click.self="emit('close')"
    @keydown.esc="emit('close')"
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
        <button aria-label="关闭" @click="emit('close')">
          <X :size="20" />
        </button>
      </header>
      <p class="muted">
        仅保存到当前浏览器的当前用户 · {{ character.name }}，不修改角色资料。
      </p>
      <div class="cover-previews">
        <div>
          <Portrait
            :source="draft.source"
            :crop="draft.crop.chat"
            :name="character.name"
          /><small>聊天封面</small>
        </div>
        <div>
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
      <footer>
        <label class="text-action upload"
          ><Upload :size="17" />选择图片<input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            @change="upload" /></label
        ><button @click="emit('close')">取消</button
        ><button class="primary" @click="emit('save', draft)">
          <Check :size="16" />保存封面
        </button>
      </footer>
    </section>
  </div>
</template>
