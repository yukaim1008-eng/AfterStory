<script setup lang="ts">
defineProps<{ source?: string }>();
</script>
<template>
  <div class="page-background" aria-hidden="true">
    <Transition name="scene"
      ><img v-if="source" :key="source" :src="source" alt=""
    /></Transition>
    <div class="ambient-light"></div>
  </div>
</template>
