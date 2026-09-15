# UI / UX 改版执行记录

范围：2026-09-14 用户授权连续执行 Phase 1–8，基于现有 F1/F2 前端改版，不修改后端、数据库或角色提示词。

## 2026-09-15 ChatPage 视觉技术债清理

- 本阶段只重构 ChatPage，没有提前改 Home、Characters、Memories 或 Settings；业务发送、失败重试、草稿、旧版本会话、历史/资料入口、记忆入口、封面调整和深链均保留。
- 删除 `style.css` 中旧 `.workspace` 的 40:60 Grid 和聊天专属骨架样式，删除 `design-system.css` 对 `.workspace` 的重复视觉接管；旧资料页所需结构改由明确的 `.secondary-workspace` 承担，页面布局不再由三个样式层共同竞争。
- 新增 `ChatCharacterScene`：同一封面拆成低强度局部模糊环境层、清晰人物层和局部穿入层，再组合主题色、渐变遮罩、局部光和底部暗部。人物层不属于左右任何一列：主肖像延伸到玻璃下方，穿入层通过水平 mask 跨越玻璃左缘；玻璃材质、人物穿入层、聊天内容分别使用 z-index 4/5/6，人物可进入聊天区域而不遮住文字与控件。
- ChatPage 根层覆盖 `100dvh` 并禁止页面级 overflow/overscroll；Chat Glass 在页头下方绝对定位，消息容器以 `flex: 1; min-height: 0; overflow: auto` 承担唯一的纵向滚动。玻璃使用 0.45–0.61 的横向透明度渐变和 7px 局部背景模糊，不再把进入面板的人物处理成无法识别的色块。
- typography 继续只使用工程内 Noto Sans SC，新增 Brand、Display、Character、Section、Body、Caption、Eyebrow 和 Handwriting Accent 的语义 token；本阶段在聊天页实际使用角色名、标题、正文、说明文字和轻量手写感引文层级。
- 空对话保留原文案但缩为轻量状态；存在消息时该状态不渲染，消息列表直接成为聊天层主体。
- 浏览器截图 `frontend/test-results/chat-desktop.png` 在固定娜娜莉主题和真实组件渲染下复查通过：角色场景覆盖完整 viewport，人物眼睛、脸部与身体轮廓清晰跨过玻璃左缘并在聊天内容下方消隐，未出现“左角色区 + 右巨大白色区”。截图为模拟 API 的视觉/交互验收，不代表真实 Provider 调用。
- 浏览器回归新增结构与滚动边界断言：场景覆盖完整 viewport、Chat Glass 绝对浮动、主肖像进入玻璃范围、穿入层具备独立 z-index 与 mask、玻璃伪元素保留 backdrop-filter；在 1440×620 短视口及各支持宽度下页面不产生纵向滚动，长消息只在 `.messages` 内滚动。
- 最终验证：`npm run build`、`npx prettier --check src tests` 和 19 项 Playwright 回归全部通过；测试自行启动并关闭 Vite，结束后 5173 端口无监听。本阶段没有真实 Provider 调用、数据库写入或服务器部署。

## 检查结论与视觉依据

- 已逐张查看 `frontend/design/GPT设计图稿/` 的设置、角色、首页和回忆参考；后续结合用户补充的聊天参考重新校正构图，明确采用“完整场景 + 独立人物层 + 玻璃材质层 + 聊天内容层”，不再使用左角色场景、右透明对话区的并列解释。
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
| 4 | 聊天页 | 沉浸式布局；发送、重试、IME、快捷键、自动滚动、深链保留 | 类型检查；15 项回归通过（更新旧文案定位后重跑相关 2 项） |
| 5 | 回忆页 | 真实历史与记忆双 Tab、筛选、原会话恢复、CRUD 与隔离 | 类型检查；7 项历史/记忆定向回归通过，覆盖分页、筛选、来源跳转、旧实例迟到响应 |
| 6 | 设置页 | 四分类，字体/快捷键/动效/封面持久化、声音诚实未启用 | 类型检查；封面、字体、语音未启用和发送方式定向回归通过 |
| 7 | 统一视觉 | 组件/字阶/玻璃层/反馈/动效/可访问性一致，素材近似说明 | 1440px 各页面截图复查、控制台零错误；900/1440/1600/1920 无横向溢出回归通过 |
| 8 | 响应式和回归 | 1440/1600/1920 及小桌面无溢出、build/typecheck/现有测试及新增回归、console 检查 | `npm run build`、Prettier 检查与 19 项 Playwright 回归全通过；900/1440/1600/1920 四档主页面均无横向溢出，控制台和 pageerror 为零 |

## 已实施

Phase 1：抽出 `useAfterStory`，沿用业务逻辑；新增 AppShell、TopNavigation、PageBackground、GlassPanel、CharacterAvatar、themeStyle 和语义设计 token。新首页路由为默认入口；旧路由继续保留。正式首页在下一阶段替换临时入口。初始工作区仅有用户未跟踪设计稿，未纳入提交。

## 暂缓与限制

正式 Canon、角色性格、自动记忆、语音、登录同步不在本轮范围。不会把设计文案变成模型提示词。真实模型效果沿用原验收；本轮主要通过受控 API 浏览器回归验证前端交互，不伪称模拟测试验证了真实 Provider。

Phase 2：首页使用独立 HomePage、GlassPanel、CharacterAvatar。Hero 显示当前角色和真实最近相见时间，最近回忆最多三条来自当前会话成功轮次及同实例手动记忆。无记录展示空态，未知日期不补造。快捷入口和底部轻量伙伴均已连接现有路由。记忆实例变化立即清空旧列表、拒绝迟到响应；装饰文案和标签放入 characters.json，不改提示词。1440 截图验证无溢出、pageerror 为零；截图用模拟数据，未写真实数据库。

Phase 3：CharactersPage 与 CharacterCard 完成，当前角色为横向主卡，其余角色响应式网格；每张卡片主题独立，hover/focus 只产生轻微位移与缩放。复查截图发现主卡按钮底部受旧选择器优先级影响，已修复并增加按钮在卡片内部的断言。

Phase 4：ChatPage 与 CharacterSidebar 的初版曾采用左角色、右玻璃对话区，已被 2026-09-15 的视觉技术债清理取代；当前为完整 viewport 场景、独立人物穿入层和浮动聊天玻璃。技术版本只保留内部属性及资料页，聊天不显示连接诊断；“加载更早消息后保留阅读位置”、Ctrl+Enter/Shift+Enter/自动滚动、真实发送函数、request_id、会话深链、草稿和重试继续沿用。

Phase 5：MemoriesPage 合并聊天片段与她记得的事，保持历史/记忆旧链接可用。历史卡片只使用真实预览、角色、轮数和时间；记忆只展示用户主动保存的内容。历史与记忆均保留清楚的“加载更多”分页，已载入记录可按角色、时间、类型和关键词筛选；角色或实例切换立刻清空旧记忆，并丢弃迟到响应。未安装角色、空记录、能力未启用与接口失败都有各自状态，不使用虚构数据补位。

Phase 6：SettingsPage 将通用、外观、声音和数据管理统一到同一骨架。现有字体、发送方式、动效、语音播放偏好、封面编辑和恢复默认继续写入原有本地存储；语音明确显示尚未启用。数据入口只跳转现有回忆页面，不新增账号、同步或数据删除功能。

Phase 7：统一使用 AppShell、PageBackground、GlassPanel、CharacterSidebar、CharacterAvatar 和语义主题 token。页面进入、角色封面切换、卡片悬停都使用短暂轻动效，并遵从动效偏好和系统减少动效设置。因没有房间、书桌和照片墙资产，背景采用现有角色插画裁切、柔光、渐变、遮罩及低透明玻璃层近似；没有使用参考图作为背景，也没有生成或下载额外素材。

Phase 8：以受控 API 跑完 19 项 Playwright 浏览器回归，覆盖一级页面、角色切换、聊天发送与快捷键、深链、历史/个人记忆分页筛选与隔离、封面/偏好持久化，以及四档桌面宽度。`npm run build` 同时完成媒体准备、`vue-tsc --noEmit` 和生产构建；`npx prettier --check src tests` 通过。项目没有配置 ESLint 或独立 `lint` 脚本，未伪造该结果。验证服务均由测试自行退出，未遗留本轮启动的前后端服务。
