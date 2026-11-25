# Refined Theme Implementation Plan

<!-- 规划简约轻科技界面的主题、布局、弹窗和验证步骤。 -->

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 统一配置中心视觉，提供可记忆的深浅主题和克制的渐变、动效。

**Architecture:** 沿用 React、CSS、原生 dialog；主题模块统一维护根元素 data-theme 与系统/用户偏好，组件只消费主题和切换接口。三份现有样式改用语义颜色变量，资源列表按状态展示。

**Tech Stack:** React 19、TypeScript、Vite、CSS；Node 自带测试运行器和临时浏览器验证工具，不增加应用依赖。

**Spec:** [设计说明](../specs/2026-11-25-refined-theme-design.md)

## Global Constraints

- 前端 3000、后端 8000；保留已有启动配置修改。
- 不改变 API、配置保存、导入与检查业务。
- 只有主题偏好进入 localStorage。
- 交互时长约 150–200ms，遵循 prefers-reduced-motion。
- 不提交依赖、浏览器产物、私密数据、本机路径；此次不自动提交和推送。

## Review Focus

- localStorage 不可读写时：应用能加载并在当前会话切换主题。
- 系统深色、刷新、手动选择：偏好优先级稳定，主题按钮标签正确。
- 错误和筛选无结果：不冒充首次使用，并能重新加载或调整条件。
- 原生 dialog、select、textarea：深色主题无白底残留，键盘焦点可见。
- 窄屏、长名称、减少动画：无页面横向溢出，表格可滚动，非必要动画禁用。

### Task 1: 主题行为与全局视觉基础

**Files:** Create `frontend/src/app/theme.ts`, `frontend/src/app/ThemeToggle.tsx`, `frontend/tests/theme.test.ts`; Modify `frontend/src/main.tsx`, `frontend/src/styles/base.css`.

**Interfaces:** 主题模块导出 `initializeTheme(): void`, `getTheme(): 'light' | 'dark'`, `toggleTheme(): void`, `subscribeTheme(listener: () => void): () => void`；ThemeToggle 无 props，使用 useSyncExternalStore。

- [x] 编写主题行为测试，验证默认系统偏好、已保存偏好、切换持久化、存储失败和系统变化；运行 Node 测试确认主题功能尚未存在。
- [x] 实现主题模块和有可访问标签的按钮，main.tsx 在 React 挂载前初始化；全局样式定义完整语义颜色和深浅主题，原生控件使用 color-scheme。
- [x] 再运行主题测试，验证全通过。

### Task 2: 壳层、列表与弹窗视觉统一

**Files:** Modify `frontend/src/app/App.tsx`, `frontend/src/app/Sidebar.tsx`, `frontend/src/features/configuration/ResourceList.tsx`, `frontend/src/features/configuration/CheckPanel.tsx`, `frontend/src/styles/configuration.css`, `frontend/src/styles/editor.css`, `frontend/README.md`.

**Interfaces:** 沿用现有资源操作回调；App 顶部挂载 ThemeToggle，所有配色消费 Task 1 语义变量。

- [x] 收紧侧栏和顶部重复信息；重新设计空态，有数据才展示搜索工具栏、表头和计数，过滤无结果仍保留工具栏。错误和读取态明确反馈。
- [x] 统一导航、表格、表单、抽屉、导入、检查、通知；添加局部渐变、150–200ms 过渡和检查运行态反馈。
- [x] 更新前端说明，记录主题行为与测试命令；运行格式检查、主题测试、类型检查和构建。

### Task 3: 浏览器验收和独立检查

**Files:** 浏览器脚本和截图存放 Git 忽略的 output/ 下，不添加应用依赖。

- [x] 使用实际浏览器测试两种主题、刷新、系统主题、存储失败、分类与所有弹窗、已有列表/筛选、375px 与减少动画；不写入用户资源，列表使用浏览器隔离响应。
- [x] 获取浅/深主题截图并目视检查；检查 HTTP、控制台和页面溢出。
- [x] 由独立检查者审核当前差异，修复影响使用的问题，完成格式、主题测试、类型、构建验证，保留开发服务运行。
