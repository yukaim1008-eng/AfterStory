<script setup lang="ts">
import type { Crop } from "./types";
defineProps<{ source: string; crop: Crop; name: string }>();
</script>
<template>
  <div class="portrait">
    <img
      :src="source"
      :alt="name"
      :style="{
        objectPosition: `${crop.x}% ${crop.y}%`,
        transform: `scale(${crop.zoom})`,
        transformOrigin: `${crop.x}% ${crop.y}%`,
      }"
    />
  </div>
</template>
