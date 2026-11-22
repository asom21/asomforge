# Backend

AsomForge 的 Python 后端，负责配置、协作定义、运行状态、人工交互、产物交接和恢复重试。

## 目录职责

| 目录 | 职责 |
| --- | --- |
| `src/asomforge/api/` | 对外 API、输入输出转换和运行事件接口 |
| `src/asomforge/application/` | 配置与运行用例、协作推进、交接和恢复的协调 |
| `src/asomforge/domain/` | Agent、Workflow、Run 等核心概念及状态规则、接口抽象 |
| `src/asomforge/infrastructure/` | 数据访问、文件存储及其他外部设施实现 |
| `src/asomforge/runtimes/` | Codex、Claude Code、通用运行时的接入适配 |
| `src/asomforge/worker/` | 后台执行入口、任务领取和执行状态回报 |
| `tests/unit/` | 领域与应用规则的单元测试预留 |
| `tests/integration/` | 存储、接口、交接与执行适配集成测试预留 |

## 模块边界

领域层不依赖具体 Web 框架、数据库或外部运行时。应用层通过抽象接口协调存储和执行；API 与 Worker 作为入口调用应用用例，基础设施和运行时适配器提供实际能力。

API 请求与长时间执行任务保持清晰边界。是否使用独立进程及具体通信方式，在后续运行设计中确定，不在当前生成实现。

## 技术方向

建议使用 FastAPI、Pydantic、SQLAlchemy、Alembic 和 uv。数据库产品、依赖版本与执行接入方式尚待确认。

当前未创建 Python 模块、应用入口、数据库迁移或依赖清单，不能直接运行服务。

参见 [工程结构](../docs/architecture/project-structure.md) 和 [开发协作规范](../AGENTS.md)。
