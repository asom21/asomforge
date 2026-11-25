// 定义配置分类、平台名称和资源摘要的展示规则。
import {
  BookOpen,
  Bot,
  Cable,
  MessageSquareText,
  Terminal,
  Wrench,
  type LucideIcon,
} from 'lucide-react';
import type { Category, Resource } from '../../api/client';

export const categories = [
  {
    key: 'skills',
    title: 'Skill',
    subtitle: '将经验与方法，整理为可复用的能力。',
    icon: BookOpen,
    hint: '导入 SKILL.md、Skill 目录或 ZIP，保留配套材料。',
  },
  {
    key: 'mcp',
    title: 'MCP',
    subtitle: '连接工具与数据，让 Agent 触达更多服务。',
    icon: Cable,
    hint: '支持 stdio、Streamable HTTP 和旧版 SSE。导入 mcpServers JSON 后可单独检查连接。',
  },
  {
    key: 'tools',
    title: 'Tool',
    subtitle: '管理本地工具，扩展 Agent 的执行能力。',
    icon: Wrench,
    hint: 'Tool 暂未开放，当前先完成其他配置。',
  },
  {
    key: 'prompts',
    title: 'Prompt',
    subtitle: '沉淀清晰的指令，让每次协作有据可循。',
    icon: MessageSquareText,
    hint: '使用 {{变量名}} 标记输入变量；支持 Markdown、纯文本与本平台 JSON。',
  },
  {
    key: 'models',
    title: '大模型',
    subtitle: '为不同任务，准备合适的模型连接。',
    icon: Bot,
    hint: '支持 OpenAI Chat Completions、Responses 和 Anthropic Messages；测试会发送一次真实文本请求。',
  },
  {
    key: 'platforms',
    title: '运行平台',
    subtitle: '连接本机的 Agent 平台，保留各自的工作方式。',
    icon: Terminal,
    hint: '支持 Codex、Claude Code、DeepSeek Harness。可为同一平台保存多份配置。',
  },
] satisfies { key: Category; title: string; subtitle: string; icon: LucideIcon; hint: string }[];

export const platformNames: Record<string, string> = {
  codex: 'Codex',
  claude: 'Claude Code',
  deepseek_harness: 'DeepSeek Harness',
};
export function summary(resource: Resource): string {
  const c = resource.config;
  switch (resource.kind) {
    case 'skills':
      return String(c.skill_name);
    case 'mcp':
      return c.type === 'stdio' ? [c.command, ...(c.args as string[])].join(' ') : String(c.url);
    case 'prompts':
      return String(c.content).replace(/\s+/g, ' ').slice(0, 90);
    case 'models':
      return [
        Array.isArray(c.models) ? `${c.models.length} 个模型` : c.model ? '1 个模型' : '目录待补全',
        c.protocol,
        c.base_url,
      ]
        .filter(Boolean)
        .join(' · ');
    case 'platforms':
      return [platformNames[String(c.platform)], c.cwd || '默认工作目录'].join(' / ');
  }
}
