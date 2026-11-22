# 技术路线

<!-- 记录已采用的技术方案、选择理由及后续待定事项。 -->

## 当前落地

配置中心采用 TypeScript 前端、Python 后端和本地文件。单个后端进程提供 API、按需连接检查与生产静态页面，不引入数据库、用户体系、任务队列或执行编排框架。

| 部分 | 已采用 | 说明 |
| --- | --- | --- |
| 界面 | React、TypeScript、Vite | 直接编写类型表单；没有动态表单引擎和大型 UI 框架 |
| 后端 | Python 3.12+、FastAPI、Pydantic | 边界结构校验与 HTTP/SSE 接口 |
| 存储 | JSON、Skill 目录、私密文件 | 普通资源按 ID 保存；Skill 保留标准包名和相对资料路径 |
| 连接 | MCP 官方 Python SDK、HTTPX | stdio、Streamable HTTP、SSE；模型只读发现 |
| 平台 | Codex、Claude Code、DeepSeek Harness 检查适配器 | 仅安装、版本及平台支持的认证状态查询 |
| 工具链 | pnpm、uv、Prettier、Ruff、pytest | 两端依赖由锁文件固定 |
| 接口类型 | OpenAPI、openapi-typescript | 从后端结构生成前端资源与请求类型 |

本次环境验证使用 Node.js 26.1.0、pnpm 10.23.0、CPython 3.12.13。当前锁定 React 19.3.1、Vite 7.3.8、TypeScript 5.9.3、FastAPI 0.129.2、Pydantic 2.14.4、MCP SDK 1.30.0 和 HTTPX 0.28.1；完整依赖以 frontend/pnpm-lock.yaml 和 backend/uv.lock 为准。

文件数据默认位于 doc/；docs/ 保存说明文档。配置可被未来多个 Agent 节点引用，平台配置不承载某条链路的占用状态或运行进度。同一数据根目录只允许一个后端实例协调写入，当前不做跨进程或跨机器同步。

## 选择理由与边界

当前要解决的是个人本机的配置管理，文件保存已能满足按类型、名称查找和编辑的需求。先采用直接文件读写与必要的原子替换，不增加 ORM、迁移和数据库运维。凭据通过引用与普通配置分开，当前没有系统凭据库或加密能力。

检查与执行分别验收。模型列表能读取，不代表生成可用；MCP 能握手，不代表业务工具可用；CLI 已认证，不代表 Agent 已成功运行。DeepSeek Harness 当前只能明确确认程序和版本，不能假定其认证查询接口。

实现参考 MCP、Agent Skills 规范及各平台公开接口。CC Switch 用于参考分类、导入和适配器职责，不移植其数据库、代理和客户端全局配置同步。具体依据见[配置中心设计](../superpowers/specs/2026-11-22-configuration-center-design.md)。

## 后续再定

画布可评估 React Flow；执行层需要在真实平台接口上设计会话、交接、人工补充和重试。A2A 版本、调度器、状态机、运行数据存储与云端数据库需求在执行阶段讨论。当前未引入 CrewAI、数据库或常驻 worker，也不为未来兼容预建多套存储实现。

后续引入依赖时核对公开文档、资源开销和可验证能力。不能因为采用某个框架而改变已确认的业务流程；功能分阶段交付，每阶段独立验证和收尾。
