<script setup lang="ts">
import Portrait from "../Portrait.vue";
import type { Character, Cover } from "../types";
defineProps<{ character: Character; cover: Cover }>();
</script>
<template>
  <Portrait
    class="character-avatar"
    :source="cover.source"
    :crop="cover.crop.chat"
    :name="character.name"
  />
</template>
