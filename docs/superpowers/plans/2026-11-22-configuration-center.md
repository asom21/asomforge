# 配置中心实施计划

<!-- 记录配置中心的实施步骤、验证结果和交付范围。 -->

> For agentic workers: 使用 executing-plans 在当前会话逐项执行；用户禁止使用 subagent。每项完成后运行对应检查。

**Goal:** 交付可启动的配置中心前后端，完成五类配置的文件保存、导入、校验与真实可用性检查。

**Architecture:** 一个本地 FastAPI 服务管理文件与外部探测，React 前端共用列表与编辑骨架。领域规则、应用用例、文件存储、检测适配按已有目录分工。

**Tech Stack:** Python 3.12+、FastAPI、Pydantic、MCP SDK、HTTPX、React、TypeScript、Vite、pnpm、uv。

**Spec:** [已确认设计](../specs/2026-11-22-configuration-center-design.md)。

## 全局约束

- 五类资源使用本地 doc/config/，凭据在 doc/private/；无数据库或用户体系。
- Tool 仅显示暂未开放，不建立读写接口。
- 运行平台覆盖 Codex、Claude Code、DeepSeek Harness，不修改原生全局配置。
- 导入预览和保存不自动连接；MCP 不调用业务工具，模型检测不生成内容。
- 共用实际重复的操作，按职责适度拆分，保留边界校验，避免空抽象和重复防御。

## Task 1：资源保存闭环

文件：backend/pyproject.toml；src/asomforge/main.py；domain/configurations.py；application/configurations.py；infrastructure/files.py；api/configurations.py；tests/integration/test_configuration_api.py。

接口：create_app(data_dir) 创建隔离数据目录的应用；GET/POST /api/configurations/{kind}；GET/PUT/DELETE /api/configurations/{kind}/{id}。更新带 revision，返回保存后的 Resource；应用用例通过领域定义的存储接口读写。

- [x] 建立 uv 环境与空 FastAPI 应用，写 HTTP 集成测试后先观察保存请求返回 404。
- [x] 实现五类结构校验、稳定 ID、版本冲突、原子文件保存及凭据引用。
- [x] 验证重建应用后仍可读取，凭据不进入响应或普通 JSON，冲突更新不覆盖数据。

```python
def test_prompt_survives_restart(tmp_path):
    client = TestClient(create_app(tmp_path))
    saved = client.post('/api/configurations/prompts', json={
        'name': '需求分析', 'config': {'content': '分析 {{goal}}', 'variables': ['goal']}
    })
    assert saved.status_code == 201
    reopened = TestClient(create_app(tmp_path))
    assert reopened.get('/api/configurations/prompts').json()[0]['name'] == '需求分析'
```

## Task 2：导入与 Skill

文件：application/imports.py；application/skills.py；infrastructure/skill_files.py；api/imports.py；tests/integration/test_imports.py。

接口：POST /api/imports/{kind}/preview 与 /commit 接收文本或 multipart 文件；返回每项名称、警告、冲突与保存结果。Skill GET/PUT 内容接口只访问该资源的 SKILL.md 和文件列表。

- [x] 先写合法 MCP、错误 args、重复处理和 ZIP 越界测试，观察失败。
- [x] 实现 mcpServers JSON、Prompt 文本、本平台 JSON 与 Skill ZIP/目录导入，预览不落盘。
- [x] 验证资源 ID 在替换时保留、另存时改变，Skill 资料保持原结构，保存失败保留原资源。

```python
def test_mcp_import_rejects_string_args(client):
    response = client.post('/api/imports/mcp/preview', json={
        'text': '{"mcpServers":{"probe":{"command":"python","args":"wrong"}}}'
    })
    assert response.status_code == 422
    assert 'args' in response.text
```

## Task 3：真实检查

文件：runtimes/checks.py；runtimes/mcp.py；runtimes/platforms.py；tests/integration/test_checks.py；tests/fixtures/mcp_server.py。

接口：POST /api/configurations/{kind}/{id}/check 流式返回检查阶段和最终结果，前端可取消请求。结果包含资源 ID、revision、工作目录与时间。

- [x] 写受控 HTTP 模型端点、MCP stdio 服务、超时及取消测试并观察失败。
- [x] 用 MCP SDK 连接和发现能力；HTTPX 读取模型列表；平台进程按参数数组检测，不启动任务。
- [x] 验证失败类型与认证限制可区分，日志不包含私密值，临时连接和进程被释放。

## Task 4：配置中心界面

文件：frontend/package.json；vite.config.ts；src/app/App.tsx；src/api/client.ts；src/features/configuration/{catalog,ConfigurationPage,ResourceEditor,ImportDialog,CheckPanel}.tsx 或 .ts；forms/；src/styles/。

接口：统一 client 访问后端资源和导入 API；类型由后端 OpenAPI 生成，表单按资源类型构造 config。

- [x] 初始化 React/Vite，生成接口类型。
- [x] 实现导航、搜索、空态、列表和侧边编辑；五类表单与 Tool 预留入口。
- [x] 实现导入预览与冲突选择、Skill 查看编辑、检查进度和取消；失败保留输入。
- [x] 运行类型检查、格式检查和构建；通过真实浏览器验证新增、编辑、导入与检查流程。

视觉基准：冷白内容底色 #F6F8FA、白色工作区 #FFFFFF、深蓝灰文字 #253345、蓝色强调 #3569D4、细边线 #E2E7EF。统一系统中文字体与清晰代码字体；以侧栏和列表的层级表达信息，避免大面积装饰渐变、等高卡片和无意义统计面板。

## Task 5：交付与审查

文件：README.md、frontend/README.md、backend/README.md、docs/decisions/technology-direction.md、AGENTS.md、示例与启动入口。

- [x] 补充真实依赖、启动与检查命令，区分已验证能力和环境缺项。
- [x] 运行后端测试与 Ruff、前端类型/格式/构建、接口类型生成一致性检查。
- [x] 对越界写入、私密泄漏、版本冲突、取消残留进程、导入部分失败和界面状态进行对抗性审查并修正。
- [x] 打开可运行预览，报告验证结果与三平台实际验证范围。

## 验收记录

2026-11-22：第一阶段已完成，配置中心、接口类型与验证说明随项目代码交付。

- 后端 31 项测试通过；Ruff 检查及格式检查通过。测试覆盖资源重启读取、版本冲突、私密值隔离、导入部分失败、ZIP 越界、三种 MCP 传输、认证失败和取消后的进程清理。
- 前端类型、Prettier 与生产构建通过；OpenAPI 和生成类型一致。生产 JS 约 258 kB，gzip 约 82 kB，未引入大型 UI 框架或状态管理库。
- 真实浏览器验证五类表单、Skill 目录导入与配套文件、MCP 导入错误反馈、新增编辑删除、未保存提醒、真实 MCP/平台检查、刷新读取与 390 px 窄屏布局。
- 对抗性审查修正：保存失败残留凭据、缺凭据导致检查流中断、HTTP 取消打断子进程清理、Windows 批处理参数包装、MCP 认证错误分类、导入元数据不匹配、来源备份失败误报、Skill 相对链接误报。
- Codex、Claude Code 的本机版本和认证状态查询通过；DeepSeek Harness 未安装，真实安装环境验证待补。没有发送模型生成请求或调用 MCP 业务工具。
- pytest 存在一条 Starlette 使用 AnyIO 旧别名的上游弃用提示，不影响测试结果。

操作方法和已知范围见[配置中心使用说明](../../configuration-center.md)。正式预览使用默认 doc/，浏览器验证数据与截图在被忽略的 output/ 下。

### 界面调整与代码整理

移除列表下方的数据目录及说明栏；五类资源加入可保存的启用状态，旧记录默认启用。切换核对版本，保留配置、凭据和 Skill 材料，编辑后继续保留停用状态。

整理启动组装、导入请求解析、编辑保存处理、导入顺序与类型定义；移除废弃页脚样式、无意义事件包装和类型断言。补充非法 UTF-8 的校验反馈。开关、刷新、编辑、冲突与 JSON/表单切换均完成浏览器验证；临时配置已清理，原有凭据与 Skill 文件校验一致。
