# AsomForge

<!-- 说明项目现状、目录、启动方式和验证命令。 -->

**AsomForge 是面向个人本地使用的 Agent 组织与协作平台。** 配置中心管理可复用资源，运行界面通过画布组织 Agent，平台按照约定执行任务、交接产物、处理人工补充并保留运行历史。

## 当前状态

当前已实现配置中心前后端：五类配置可新增、编辑、删除、导入和独立检查，数据保存在本机文件中。大模型连接支持一份 API 连接管理多个模型、发现候选目录，以及按 OpenAI Chat Completions、Responses、Anthropic Messages 协议发起明确触发的文本连通性测试。Tool 仅保留入口。画布、Agent 执行、调度与恢复引擎尚未实现。

第一阶段已确定为配置中心闭环：使用本地文件保存和管理 Skill、MCP、Prompt、大模型和运行平台配置，支持导入及适用的校验与连通性测试。Tool 保留导航和目录位置，暂不实现。后续功能分阶段设计、验证和验收。

## 项目资料

- [项目介绍](./AsomForge-项目介绍.md)：面向初次了解项目的读者。
- [项目说明与架构设计](./AsomForge-项目说明与架构设计.md)：产品边界、逻辑架构与核心概念。
- [工程结构](./docs/architecture/project-structure.md)：目录职责和模块依赖方向。
- [本地数据目录](./doc/README.md)：配置、私密数据和日志的固定目录约定。
- [技术路线](./docs/decisions/technology-direction.md)：已选择的语言方向与待确认的技术建议。
- [Agent 开发协作规范](./AGENTS.md)：后续代码助手需要遵循的项目约定。

## 目录

```text
AsomForge/
├── README.md
├── AGENTS.md
├── .gitignore
├── .editorconfig
├── AsomForge-项目介绍.md
├── AsomForge-项目说明与架构设计.md
├── frontend/                 # TypeScript 前端
│   ├── README.md
│   ├── src/
│   │   ├── app/              # 应用入口、路由和页面组合
│   │   ├── features/
│   │   │   ├── configuration/ # 配置中心
│   │   │   ├── workflows/     # 链路画布与定义管理
│   │   │   └── runs/          # 执行详情、对话与产物
│   │   ├── components/       # 通用界面组件
│   │   ├── api/              # 后端接口访问
│   │   └── types/            # 前端类型与接口类型入口
│   ├── public/               # 静态资源
│   └── tests/                # 前端测试预留
├── backend/                  # Python 后端
│   ├── README.md
│   ├── src/asomforge/
│   │   ├── api/              # HTTP 与事件接口
│   │   ├── application/      # 用例、协作推进和交接协调
│   │   ├── domain/           # 核心概念、状态与规则
│   │   ├── infrastructure/   # 存储及外部设施实现
│   │   ├── runtimes/         # 执行环境适配
│   │   └── worker/           # 后台执行入口与任务领取
│   └── tests/
│       ├── unit/
│       └── integration/
├── doc/                      # 本地数据；除目录说明外不提交
│   ├── README.md             # 固定目录与保存约定
│   ├── config/               # 按资源类型保存配置与资源
│   ├── private/              # 本机私密数据
│   └── logs/                 # 本地应用日志
└── docs/
    ├── README.md
    ├── architecture/         # 工程与系统设计
    ├── decisions/            # 技术选型和决策记录
    └── contracts/            # 接口与产物契约说明
```

空目录通过 `.gitkeep` 保留，添加实际文件后可移除对应占位文件。

## 技术方向

采用 React、TypeScript、Vite 前端与 Python、FastAPI、Pydantic 后端，在一个仓库中维护。pnpm 与 uv 分别管理依赖，版本由锁文件固定。React Flow 和执行编排框架尚未引入。

当前交付面向个人电脑运行，不建设登录、注册、多用户或租户体系。界面、后端和 Agent 执行在本地，配置中心以 doc/ 下的文件为准，不引入本地或云端数据库。本地应用停止时任务不继续执行，后续运行记录的存储方式另行设计。

大模型连接与运行平台配置分别管理。执行层通过适配器连接 Codex、Claude Code 或通用 Agent 运行时，具体框架版本、执行接入、恢复实现以及后续数据库需求仍待讨论。

## 开发与启动

需要 Node.js 22.12+、pnpm 10、Python 3.12+ 与 uv。默认开发方式为前后端分开运行：前端使用 3000 端口，后端使用 8000 端口。

首次在项目根目录安装依赖：

```powershell
pnpm --dir frontend install --frozen-lockfile
uv sync --project backend --locked --link-mode copy
```

在项目根目录打开两个终端，分别启动服务。

终端一，启动后端：

```powershell
uv run --project backend python -m asomforge
```

终端二，启动前端：

```powershell
pnpm --dir frontend dev
```

浏览器打开 http://127.0.0.1:3000。前端支持热更新，`/api` 请求由 Vite 代理到 http://127.0.0.1:8000；后端接口文档位于 http://127.0.0.1:8000/docs。前端端口被占用时会报错，不自动切换到其他端口。

两个服务默认只监听本机。后端数据根目录为 doc/，可用 `--data-dir`、`--port` 调整；修改后端端口时，也需同步调整 frontend/vite.config.ts 中的 API 代理目标。

生产构建可执行 `pnpm --dir frontend build`，构建产物由后端一并提供，此时可直接访问后端地址；该方式不提供前端开发热更新。

常用验证命令：

```powershell
uv run --project backend pytest backend/tests -q
uv run --project backend ruff check backend/src backend/tests
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend format:check
pnpm --dir frontend build
```

导入格式、检查范围与数据备份见[配置中心使用说明](./docs/configuration-center.md)。

## 后续产品范围

- 配置中心和运行界面是两大产品入口；运行界面包含画布与运行详情。
- 用户在画布上组织 Agent，平台按定义推进工作。
- 通过正式产物及约定格式自动进行上下游交接。
- 支持任务中的提问、回答及运行历史追溯。
- 通过持久化状态、检查点和执行尝试支持恢复与重试。
- 第一版不实现自主分派和跨任务长期记忆。
