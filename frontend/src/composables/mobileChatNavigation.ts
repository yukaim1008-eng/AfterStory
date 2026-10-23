import { ref } from "vue";

const chatOrigin = ref<string>();

/** The origin is intentionally ephemeral: a direct chat link returns to Characters. */
export function rememberChatOrigin(next: string, previous?: string) {
  if (next === "chat")
    chatOrigin.value = previous && previous !== "chat" ? previous : undefined;
}

export function returnFromChat(route: (page: string) => void) {
  route(chatOrigin.value || "characters");
}
