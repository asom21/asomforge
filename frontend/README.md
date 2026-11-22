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

开发服务只绑定本机；`/api` 代理到 127.0.0.1:8000。生产构建输出 dist/，由后端提供。修改接口后先在 backend/ 导出 OpenAPI，再执行 `pnpm api:generate`。

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

五类资源共用操作流程，类型字段直接用组件表达，不维护动态表单引擎。保存失败保留输入；离开未保存的编辑区会提醒；检查始终针对已保存版本。Tool 仅展示暂未开放。画布和运行详情仍未实现。
