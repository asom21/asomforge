# Frontend

AsomForge 的 TypeScript 前端，承担配置中心、协作画布和运行详情界面。

## 目录职责

| 目录 | 职责 |
| --- | --- |
| `src/app/` | 应用初始化、路由、布局与页面组合 |
| `src/features/configuration/` | Agent、Skill、MCP、Tool 与执行配置管理 |
| `src/features/workflows/` | 链路画布、节点配置、协作关系和定义版本 |
| `src/features/runs/` | 本次执行进度、历史、对话与产物查看 |
| `src/components/` | 与具体业务场景无关的通用组件 |
| `src/api/` | 后端请求、事件订阅和错误处理 |
| `src/types/` | 界面类型以及后续生成接口类型的接入位置 |
| `public/` | 需要直接发布的静态资源 |
| `tests/` | 前端交互与集成测试预留 |

## 技术方向

建议使用 React、Vite 和 React Flow。当前尚未创建依赖清单、组件、路由或工具配置。

前端管理交互状态，运行事实由后端持久化。后续应以接口契约为依据接入数据，避免手工维护两套不一致的业务契约。

参见 [项目入口](../README.md) 和 [技术路线](../docs/decisions/technology-direction.md)。
