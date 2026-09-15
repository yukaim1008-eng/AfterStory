<script setup lang="ts">
import type { Crop } from "./types";
defineProps<{
  source: string;
  crop: Crop;
  name: string;
  position?: string;
}>();
</script>
<template>
  <div class="portrait">
    <img
      :src="source"
      :alt="name"
      :style="{
        objectPosition: position || `${crop.x}% ${crop.y}%`,
        transform: `scale(${crop.zoom})`,
        transformOrigin: position || `${crop.x}% ${crop.y}%`,
      }"
    />
  </div>
</template>
