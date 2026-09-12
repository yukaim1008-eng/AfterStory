# AfterStory 前端

当前为 F1 可运行前端。用户已认可设计并授权开发，先跑通页面与文字链路，再收集角色数据、优化效果；完整 V1 尚未验收。

## 启动

按 [运行说明](../docs/running-frontend.md) 启动数据库和后端，再在本目录执行：

```powershell
npm ci
npm run dev
```

打开 http://127.0.0.1:5173 。默认代理后端 http://127.0.0.1:8000 ，均仅监听本机。

## 当前可测试

- 三位主角色主题、悬停展开选择、聊天、资料、历史和四类设置。
- 真实文字发送、失败重试、草稿保留、刷新恢复与历史分页加载。
- 字体、发送快捷键、动效偏好；封面上传、两处独立裁切、取消、保存与恢复默认。
- 语音、个人记忆显示尚未启用；剧情进度待补全，不模拟接口成功。

## 可更改数据

| 内容 | 位置 |
| --- | --- |
| 角色名称、介绍、主题、封面、裁切、发送按钮图片与文案 | [public/characters.json](public/characters.json) |
| 默认封面 | data/character-assets/{id}.png；更改后运行 npm run prepare:media |
| 当前用户封面 | 浏览器 IndexedDB，按后端用户与角色隔离 |
| 偏好与草稿 | 浏览器 localStorage，按后端用户隔离 |
| 联调性格提示词 | [companions.integration.json](../fixtures/companions.integration.json)；新增版本后导入，不覆盖旧版本 |

三张默认插画为官方形象的生成式参考，不是正式角色资产。当前介绍和提示词是联调资料，不是完整 Canon。个性化发送按钮待性格补全后再设计。

## 设计依据与验证

沿用 [data 中认可的效果](../data/design-preview/full-desktop-review/README.md)，控件以 [09 修订](../data/design-preview/full-desktop-review/09-controls-refinement.png) 为准。当前范围见 [06 前端](../docs/design/06-frontend.md)，不恢复早期深蓝色设计。

```powershell
npm run build
npx playwright install chromium
npm run test:e2e
```

自动浏览器测试模拟 API；手动真实链路脚本 scripts/smoke-real.mjs 使用独立后端身份，详见运行说明。
