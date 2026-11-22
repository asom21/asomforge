# 后端

<!-- 说明后端职责、启动配置、接口入口和检查命令。 -->

Python 3.12+、FastAPI、Pydantic。单个本地服务负责配置保存、导入和检查，不引入数据库、用户体系、任务队列或独立 worker。

在本目录执行：

```powershell
uv sync --locked --link-mode copy
uv run python -m asomforge
uv run pytest -q
uv run ruff check src tests
uv run ruff format --check src tests
```

默认监听 127.0.0.1:8000；前端 dist/ 存在时一并提供静态页面。`python -m asomforge --data-dir <目录> --port <端口>` 可覆盖默认位置。API 文档见 `/docs`。

| 环境变量 | 默认值 | 用途 |
| --- | --- | --- |
| ASOMFORGE_DATA_DIR | 项目 doc/ | 数据根目录；CLI 参数优先 |
| ASOMFORGE_CHECK_TIMEOUT | 20 | 每次检查总时限，单位秒，包含排队时间 |
| ASOMFORGE_CHECK_CONCURRENCY | 3 | 同时执行的检查数；需为正整数 |
| ASOMFORGE_IMPORT_LIMIT | 16777216 | 导入文件及解压后内容的大小上限，单位字节 |
| ASOMFORGE_LOG_LEVEL | info | 服务日志等级 |

资源接口在 `/api/configurations/{kind}`；导入在 `/api/imports/{kind}/preview` 和 `/commit`；检查使用 POST `/api/configurations/{kind}/{id}/check`，返回 SSE。客户端断开后取消检查并释放连接、子进程。Tool 不在可写类型中。

PATCH `/api/configurations/{kind}/{id}` 接收 `enabled` 布尔值和当前 `revision`，只切换启用状态；保留正文、配套文件和凭据，过期版本返回 409。旧资源缺少 enabled 字段时按启用读取。

`domain/` 定义资源和结构规则，`application/` 实现保存与导入，`infrastructure/` 实现文件仓储，`runtimes/` 放连接检查适配器，`api/` 处理 HTTP，`main.py` 组装应用。worker/ 仍是后续执行阶段的预留目录。

更新接口后在本目录执行 `uv run python -m asomforge.export_openapi`，再到前端执行 `pnpm api:generate`。提交 OpenAPI 与生成类型，避免两端手工维护同一份接口结构。

检查与限制见[配置中心说明](../docs/configuration-center.md)。同一数据根目录只运行一个后端实例。
