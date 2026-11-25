# Model Connections Implementation Plan

<!-- 规划多模型连接、协议测试及前端目录编辑的实施接口与验证。 -->

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for inline work, with one scoped backend implementer running against the frozen API below.

**Goal:** 实现已批准的多模型连接、模型发现和指定消息的真实连通性测试。
**Architecture:** 领域模型规范化旧配置；独立 HTTP 适配器负责三种协议；模型操作服务负责草稿凭据与保存版本校验。前端单独模型编辑器消费生成契约，不扩展通用字符串表单。
**Tech Stack:** Python/FastAPI/Pydantic/HTTPX；React/TypeScript/Vite/CSS；pytest/Ruff、Node 测试和真实浏览器。
**Spec:** [已批准设计](../specs/2026-11-25-model-connections-design.md)

## Global Constraints

- 消息固定为“请只回复：连接成功。不要执行命令或修改文件。”，无工具，单次请求，不自动重试。
- 默认总超时20秒、并发3，响应实际解压后上限4MiB，输出预算不超过1024。
- 只用受控本地接口验证，不使用现有用户密钥请求付费模型。
- 保留现有分支与未提交界面修改，前端3000/后端8000；不自动提交或推送。
- 新文件顶部中文职责说明；同步OpenAPI与前端类型、中文文档和示例。

## Review Focus

- 草稿密钥为空/明确清除/过期revision：只按明确规则复用凭据，不泄漏。
- 测试时修改/删除资源或关闭窗口：不将旧结果写入新版本，不保存取消结果。
- 三种协议、非标准模型发现、超限/工具响应：明确分类，不误标为生成成功。
- 多模型增删、默认选择、容量与档位：不丢配置，草稿结果随相关输入变更失效。
- 深浅主题与窄屏/长目录：保持单内容滚动，操作可达。

## Frozen API

Model config: `{ protocol, base_url, api_key, output_token_field?, models: ModelEntry[], default_model_id }`。ModelEntry: `{id,name?,context_window?,max_output_tokens?,input_modalities:['text'|'image',...],reasoning_efforts?:false|Record<off|minimal|low|medium|high|xhigh,string|null>}`。

- POST `/api/model-connections/discover` JSON `{config,resource_id?,revision?,clear_api_key?:boolean}` => `{models:ModelEntry[]}`。发现允许空目录，不要求资源名称。
- POST `/api/model-connections/test` JSON 上述字段及 `{model_id,reasoning_effort?:string}` => SSE running/final；只测试草稿，永不写资源/密钥/结果。
- POST `/api/configurations/models/{id}/test` JSON `{revision,model_id,reasoning_effort?:string}` => SSE；只测已保存版本并在同版本时登记结果。
- 原 `/api/configurations/models/{id}/check` 默认测默认模型，其他资源维持现有逻辑。
- 统一 final 为现有 CheckResult 外形，draft resource_id为空字符串/revision=0；details: `{mode:'generation',model_id,model_name?,reasoning_effort?,latency_ms,response_preview?,persisted?:boolean}`。Resource 增加 `model_checks: Record<string,CheckResult>` 默认空；last_check 保持最近一次。
- 协议字符串 `openai-chat-completions|openai-responses|anthropic-messages`；Chat output_token_field 默认max_completion_tokens，可选max_tokens。非Chat不发送该参数，推理仅前两种协议适配。
- 保存时允许老字段输入规范化，但至少一个模型；读取旧空目录不重写文件。

### Task 1: 后端模型结构、HTTP适配、生命周期与API

Files: 新建 domain/model_connections.py、runtimes/model_connections.py、application/model_connections.py、api/model_connections.py；按需修改 configurations.py、files.py、checks.py、main.py、contracts.py。增加 backend/tests/integration/test_model_connections.py，按新检查语义更新旧模型测试。

- [x] 基线测试与先写失败用例：旧配置兼容、3种协议准确消息/认证/预算、发现候选、草稿不落盘、凭据隔离、revision竞争、取消/超时/限流/响应上限。
- [x] 实现运行时校验和向后兼容；模型检查元数据不混入普通模型声明。
- [x] 实现发现与单模型文本测试，复用共享并发/超时和SSE取消；本地网络适配独立于业务模型。
- [x] 全量pytest与Ruff通过；导出OpenAPI。报告新增接口及任何契约偏差。

### Task 2: 多模型编辑、发现与测试前端

Files: 新建 models/values.ts、ModelConnectionEditor.tsx、ModelCatalogEditor.tsx、ModelProbe.tsx、ModelCheckDialog.tsx、api/models.ts、styles/models.css；修改App.tsx挂载、catalog.ts摘要、ResourceList.tsx状态。ResourceEditor与通用字段不再承担models，保留其他资源功能。

- [x] Node行为测试先覆盖容量解析、旧目录转化、模型验证和候选合并；运行失败后实现纯表单转换。
- [x] 生成类型接入API，使用AbortController与流事件接收，错误统一可读。
- [x] 居中编辑器支持连接信息、密钥清除、模型目录、默认模型、展开能力、推理映射、发现勾选；表单草稿保存/脏状态正确。
- [x] 测试面板显示固定消息、预算提示、模型/档位、结果与失效状态；列表已保存测试与草稿临时测试区分。
- [x] 类型、格式、构建、Node测试通过。

### Task 3: 集成、文档与浏览器验收

Files: 更新 README.md、backend/README.md、docs/configuration-center.md、docs/decisions/technology-direction.md、docs/examples/model.json 和就近说明。

- [x] 重启8000后端使新接口生效，保持3000前端运行。
- [x] 用隔离受控HTTP端点及临时资源验证保存/发现/三个协议测试、版本有效期和弹窗；测试数据不使用用户凭据。
- [x] 独立代码检查，修复影响使用的发现；全量pytest/Ruff、前端测试/格式/类型/构建及浏览器通过。
- [x] 核实服务URL、保留未提交改动并报告真实验证范围。
