# UI / UX 改版执行记录

范围：2026-09-14 用户授权连续执行 Phase 1–8，基于现有 F1/F2 前端改版，不修改后端、数据库或角色提示词。

## 检查结论与视觉依据

- 已逐张查看 `frontend/design/GPT设计图稿/` 全部四张图片：`image.png` 设置、`image copy.png` 角色、`image copy 2.png` 首页、`image copy 3.png` 回忆。目录没有单独聊天稿，按用户文字指定的左角色场景、右透明对话区实施。
- Vue 3 + TypeScript + Vite；Hash 路由、Vue reactive/ref；原生 CSS、Lucide 图标、本地 Noto Sans SC；无 Tailwind / Pinia / Vue Router。
- 原始 `App.vue` 同时承载状态与所有页面；`Portrait.vue` 和 `CoverEditor.vue` 可复用。`api.ts`、`storage.ts` 封装请求、IndexedDB；偏好与草稿按后端身份写 localStorage。
- `public/characters.json` 定义角色、版本、主题、封面、裁切与发送控件。默认图片由 `data/character-assets` 准备到 `public/media`；头像可复用封面裁切。
- 业务边界：当前为完整文字回复，无 stream/TTS/自动记忆；历史时间允许未知；记忆归属 instance，旧版本实例不可混用。
- 设计优先级为布局、信息层级、角色存在感、氛围、配色、装饰。使用已有插画与 CSS 柔光、遮罩近似场景，不使用参考截图作为页面背景，不新增图片生成或素材下载。

## 信息架构

一级：首页、角色、回忆、设置。聊天是选定角色的空间；角色资料仍为二级页面。
保留 `#/chat/:character?conversation=...&turn=...` 深链以及 `#/history/:character`、`#/memory/:character` 兼容地址。回忆用聊天片段/她记得的事双 Tab 统一展示。

## 阶段与验收

每阶段独立检查、文档同步、提交；检查失败先修复，不并行改写共享状态。

| 阶段 | 范围 | 验收输入与预期、边界 | 证据 |
| --- | --- | --- | --- |
| 1 | Theme / Layout / Navigation | 四个一级入口，角色主题兼容旧字段；旧深链、发送及隔离保留 | vue-tsc 通过；原有 10 项 Playwright 全通过；diff 检查通过 |
| 2 | 首页 | 当前角色 Hero、真实最近记录、继续聊天、轻量其他角色；空/失败/实例切换不混用记忆 | vue-tsc、1440 截图通过；13 项浏览器回归通过 |
| 3 | 角色页 | 当前角色突出，其他角色可扩展；hover 不切换身份、点击才切换 | 类型检查；角色切换回归、8 角色扩展与 900/1440 溢出检查通过 |
| 4 | 聊天页 | 沉浸式布局；发送、重试、IME、快捷键、自动滚动、深链保留 | 待实施 |
| 5 | 回忆页 | 真实历史与记忆双 Tab、筛选、原会话恢复、CRUD 与隔离 | 待实施 |
| 6 | 设置页 | 四分类，字体/快捷键/动效/封面持久化、声音诚实未启用 | 待实施 |
| 7 | 统一视觉 | 组件/字阶/玻璃层/反馈/动效/可访问性一致，素材近似说明 | 待实施 |
| 8 | 响应式和回归 | 1440/1600/1920 及小桌面无溢出、build/typecheck/现有测试及新增回归、console 检查 | 待实施 |

## 已实施

Phase 1：抽出 `useAfterStory`，沿用业务逻辑；新增 AppShell、TopNavigation、PageBackground、GlassPanel、CharacterAvatar、themeStyle 和语义设计 token。新首页路由为默认入口；旧路由继续保留。正式首页在下一阶段替换临时入口。初始工作区仅有用户未跟踪设计稿，未纳入提交。

## 暂缓与限制

正式 Canon、角色性格、自动记忆、语音、登录同步不在本轮范围。不会把设计文案变成模型提示词。真实模型效果沿用原验收；本轮主要通过受控 API 浏览器回归验证前端交互，不伪称模拟测试验证了真实 Provider。

Phase 2：首页使用独立 HomePage、GlassPanel、CharacterAvatar。Hero 显示当前角色和真实最近相见时间，最近回忆最多三条来自当前会话成功轮次及同实例手动记忆。无记录展示空态，未知日期不补造。快捷入口和底部轻量伙伴均已连接现有路由。记忆实例变化立即清空旧列表、拒绝迟到响应；装饰文案和标签放入 characters.json，不改提示词。1440 截图验证无溢出、pageerror 为零；截图用模拟数据，未写真实数据库。

Phase 3：CharactersPage 与 CharacterCard 完成，当前角色为横向主卡，其余角色响应式网格；每张卡片主题独立，hover/focus 只产生轻微位移与缩放。复查截图发现主卡按钮底部受旧选择器优先级影响，已修复并增加按钮在卡片内部的断言。
