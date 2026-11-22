# AsomForge

**AsomForge 是一个 Agent 组织与协作平台。** 用户在画布上定义角色、能力和协作关系，平台按照约定执行任务、交接产物、处理人工补充并保留运行历史。

## 当前状态

本仓库处于工程骨架阶段，包含目录、说明文档和开发约定。尚未生成应用入口、页面、接口、执行引擎、数据库模型或测试实现，当前不能启动运行。

## 项目资料

- [项目介绍](./AsomForge-项目介绍.md)：面向初次了解项目的读者。
- [项目说明与架构设计](./AsomForge-项目说明与架构设计.md)：产品边界、逻辑架构与核心概念。
- [工程结构](./docs/architecture/project-structure.md)：目录职责和模块依赖方向。
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
└── docs/
    ├── README.md
    ├── architecture/         # 工程与系统设计
    ├── decisions/            # 技术选型和决策记录
    └── contracts/            # 接口与产物契约说明
```

空目录通过 `.gitkeep` 保留，添加实际文件后可移除对应占位文件。

## 技术方向

采用 TypeScript 前端与 Python 后端，在一个仓库中维护。React、Vite、React Flow、FastAPI 等为当前建议，具体依赖与版本尚未落地。

本机运行和服务器部署复用相同的协作模型。前端展示与交互，后端管理运行状态，执行层通过适配器连接 Codex、Claude Code 或通用 Agent 运行时。

## 开发与启动

依赖清单、工具链配置和启动命令将在后续初始化阶段确定。当前不提供安装、运行或测试命令，避免把规划中的命令写成已可用能力。

## 第一版边界

- 用户在画布上组织 Agent，平台按定义推进工作。
- 通过正式产物及约定格式自动进行上下游交接。
- 支持任务中的提问、回答及运行历史追溯。
- 通过持久化状态、检查点和执行尝试支持恢复与重试。
- 第一版不实现自主分派和跨任务长期记忆。
