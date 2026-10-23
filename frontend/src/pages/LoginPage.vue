<script setup lang="ts">
import { ref } from "vue";
import { errorText } from "../api";
import { useAfterStory } from "../composables/useAfterStory";

const { login, register } = useAfterStory();
const mode = ref<"login" | "register">("login");
const username = ref("");
const password = ref("");
const showPassword = ref(false);
const inviteCode = ref("");
const busy = ref(false);
const error = ref("");

async function submit() {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    if (mode.value === "register") {
      await register(username.value, password.value, inviteCode.value);
      inviteCode.value = "";
    } else {
      await login(username.value, password.value);
    }
    password.value = "";
  } catch (cause) {
    error.value = mode.value === "login" && cause instanceof Error && cause.message === "invalid_credentials"
      ? "用户名或密码不正确。" : errorText(cause);
  } finally {
    busy.value = false;
  }
}

function switchMode() {
  mode.value = mode.value === "login" ? "register" : "login";
  password.value = "";
  inviteCode.value = "";
  error.value = "";
}
</script>

<template>
  <main class="login-page">
    <section class="login-card" aria-labelledby="login-title">
      <span class="login-brand">AfterStory ♡</span>
      <p class="login-eyebrow">{{ mode === "login" ? "WELCOME BACK" : "JOIN THE STORY" }}</p>
      <h1 id="login-title">{{ mode === "login" ? "回到故事里" : "开启你的故事" }}</h1>
      <p class="login-description">{{ mode === "login" ? "登录后，继续你和角色之间的对话。" : "填写管理员给你的邀请码，创建自己的账号。" }}</p>
      <form @submit.prevent="submit">
        <label for="login-username">用户名</label>
        <input id="login-username" v-model="username" autocomplete="username" required :maxlength="mode === 'register' ? 32 : 64" :pattern="mode === 'register' ? '[A-Za-z][A-Za-z0-9_.-]{2,31}' : undefined" :title="mode === 'register' ? '3–32 位，以字母开头，可使用字母、数字、点、下划线和连字符' : undefined" />
        <label for="login-password">密码</label>
        <div class="password-field">
          <input id="login-password" v-model="password" :type="showPassword ? 'text' : 'password'" :autocomplete="mode === 'register' ? 'new-password' : 'current-password'" required :minlength="mode === 'register' ? 12 : 1" maxlength="128" />
          <button type="button" class="password-visibility" :aria-label="showPassword ? '隐藏密码' : '显示密码'" :aria-pressed="showPassword" @click="showPassword = !showPassword">{{ showPassword ? "隐藏" : "显示" }}</button>
        </div>
        <template v-if="mode === 'register'">
          <label for="login-invite">邀请码</label>
          <input id="login-invite" v-model="inviteCode" autocomplete="off" required maxlength="43" />
        </template>
        <p v-if="error" class="login-error" role="alert">{{ error }}</p>
        <button type="submit" :disabled="busy">{{ busy ? "请稍候…" : mode === "login" ? "登录" : "注册并进入" }}</button>
      </form>
      <p class="login-note">{{ mode === "login" ? "已有邀请码？" : "已有账号？" }}<button type="button" class="login-switch" :disabled="busy" @click="switchMode">{{ mode === "login" ? "使用邀请码注册" : "返回登录" }}</button></p>
      <p v-if="mode === 'login'" class="login-note login-help">如忘记密码，请联系管理员重设。</p>
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
.login-help { margin-top: 8px; }
.login-switch { display: inline; margin: 0 0 0 7px; padding: 0; background: none; color: #a94c81; font-size: 12px; font-weight: 700; }
.login-switch:disabled { opacity: .65; }
.password-field { position: relative; min-width: 0; }
.password-field input { padding-right: 68px; }
.password-visibility { position: absolute; inset: 0 0 0 auto; min-width: 58px; min-height: 44px; margin: 0; padding: 0 10px; border-radius: 0 12px 12px 0; background: transparent; color: #a94c81; font-size: 13px; }
@media (max-width: 760px),
  (pointer: coarse) and (max-height: 500px) and (max-width: 1023px) {
  .login-page { display: block; min-height: 100dvh; min-height: 100svh; padding: max(18px, env(safe-area-inset-top)) 16px max(24px, env(safe-area-inset-bottom)); overflow: visible; }
  .login-card { box-sizing: border-box; margin: min(7vh, 48px) auto 0; padding: 24px 20px; }
  .login-eyebrow { margin-top: 20px; }
  h1 { font-size: 27px; }
  .login-description { margin-bottom: 19px; }
  input { min-height: 48px; font-size: 16px; }
  form > button { min-height: 48px; }
  .login-switch { min-height: 44px; padding: 10px 0; }
}
</style>
