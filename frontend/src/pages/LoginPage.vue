<script setup lang="ts">
import { ref } from "vue";
import { errorText } from "../api";
import { useAfterStory } from "../composables/useAfterStory";

const { login } = useAfterStory();
const username = ref("");
const password = ref("");
const busy = ref(false);
const error = ref("");

async function submit() {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    await login(username.value, password.value);
    password.value = "";
  } catch (cause) {
    error.value = cause instanceof Error && cause.message === "invalid_credentials"
      ? "用户名或密码不正确。" : errorText(cause);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-card" aria-labelledby="login-title">
      <span class="login-brand">AfterStory ♡</span>
      <p class="login-eyebrow">WELCOME BACK</p>
      <h1 id="login-title">回到故事里</h1>
      <p class="login-description">登录后，继续你和角色之间的对话。</p>
      <form @submit.prevent="submit">
        <label for="login-username">用户名</label>
        <input id="login-username" v-model="username" autocomplete="username" required maxlength="64" />
        <label for="login-password">密码</label>
        <input id="login-password" v-model="password" type="password" autocomplete="current-password" required />
        <p v-if="error" class="login-error" role="alert">{{ error }}</p>
        <button type="submit" :disabled="busy">{{ busy ? "正在登录…" : "登录" }}</button>
      </form>
      <p class="login-note">账号由管理员创建。如忘记密码，请联系管理员重设。</p>
    </section>
  </main>
</template>

<style scoped>
.login-page { min-height: 100dvh; display: grid; place-items: center; padding: 24px; background: radial-gradient(circle at 20% 15%, #ffdfec, transparent 40%), linear-gradient(135deg, #fff7f5, #eae8ff); color: #39343e; }
.login-card { width: min(100%, 420px); padding: 38px; border: 1px solid #ffffffd9; border-radius: 28px; background: #fffffff0; box-shadow: 0 20px 70px #513a6320; }
.login-brand { color: #b25183; font-size: 22px; font-weight: 800; }
.login-eyebrow { margin: 28px 0 7px; color: #aa8b9d; font-size: 11px; letter-spacing: .22em; }
h1 { margin: 0; font-size: 32px; }
.login-description { margin: 10px 0 27px; color: #77717d; }
form { display: grid; gap: 9px; }
label { margin-top: 8px; font-weight: 650; font-size: 14px; }
input { width: 100%; box-sizing: border-box; border: 1px solid #d8cfd8; border-radius: 12px; padding: 13px 14px; background: #fff; color: #39343e; font: inherit; }
input:focus { outline: 2px solid #d89abe; outline-offset: 1px; }
button { margin-top: 17px; border: 0; border-radius: 13px; padding: 13px; background: #bc6797; color: #fff; font: inherit; font-weight: 700; cursor: pointer; }
button:disabled { opacity: .65; cursor: wait; }
.login-error { margin: 3px 0 0; color: #b43850; font-size: 13px; }
.login-note { margin: 24px 0 0; color: #8b8490; font-size: 12px; line-height: 1.6; }
</style>
