# 前端

<!-- 说明前端职责、工具配置、开发启动和构建方法。 -->

React、TypeScript、Vite；使用浏览器原生 dialog 和轻量图标组件。配置以服务端文件为准，前端不在 localStorage 中保存配置或凭据。

在本目录执行：

```powershell
pnpm install --frozen-lockfile
pnpm dev
pnpm typecheck
pnpm format:check
pnpm build
```

开发时先按[后端说明](../backend/README.md)启动后端，再在本目录执行 `pnpm dev`，打开 http://127.0.0.1:3000。开发服务只绑定本机，固定使用 3000 端口；端口占用时报错，不自动切换。`/api` 代理到 http://127.0.0.1:8000。生产构建输出 dist/，由后端提供。修改接口后先在 backend/ 导出 OpenAPI，再执行 `pnpm api:generate`。

前端仅在 localStorage 中保存 `asomforge.theme` 主题偏好：首次跟随系统，右上角按钮可切换并记住选择；浏览器禁用存储时仍能在本次会话内切换。浅色与深色覆盖资源页面及编辑、导入、检查窗口。渐变限于重点元素，普通交互过渡约 150–200ms；主题切换以按钮中心为圆心，用约 550ms 向外展开新主题。系统开启减少动态或浏览器不支持视图过渡时，主题直接切换。

主题与模型表单行为使用 Node 自带测试运行器，在本目录执行 `pnpm test`（或 `node --experimental-strip-types --test tests/*.test.ts`）。模型专用模块在 features/configuration/models/，负责嵌套目录、候选选择、能力与推理映射、草稿临时测试和保存版本测试。生成接口类型作为模型字段来源；配置和密钥不会进入 localStorage。

以下配置保持标准 JSON 格式，用途在此记录：

| 文件             | 用途                                             |
| ---------------- | ------------------------------------------------ |
| package.json     | 声明前端依赖、包管理工具和开发构建命令。         |
| tsconfig.json    | 配置 TypeScript 的类型检查、模块解析和编译约束。 |
| .prettierrc.json | 统一前端代码的引号、换行和排版规则。             |

- app/：应用组合、分类导航与页面状态。
- features/configuration/：资源列表、编辑、导入、检查和各类型字段。
- components/：实际复用的弹层。
- api/：统一请求入口与 OpenAPI 生成类型。
- styles/：基础、页面和编辑弹层样式。

五类资源共用列表与导入流程；模型连接使用专门的多模型目录表单，其余类型字段直接用组件表达，不维护动态表单引擎。保存失败保留输入；离开未保存的编辑区会提醒。普通检查针对已保存版本，模型草稿测试仅临时显示结果，相关输入变化后标记过期。Tool 仅展示暂未开放。画布和运行详情仍未实现。
