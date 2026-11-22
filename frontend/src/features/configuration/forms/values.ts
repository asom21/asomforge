// 在配置资源、表单值与保存请求之间转换数据。
import type { Draft, Kind, Resource } from '../../../api/client';

export interface Values {
  name: string;
  description: string;
  content: string;
  variables: string;
  protocol: string;
  baseUrl: string;
  model: string;
  apiKey: string;
  platform: string;
  command: string;
  args: string;
  env: string;
  headers: string;
  transport: string;
  url: string;
  cwd: string;
}

export function initialValues(
  kind: Kind,
  resource?: Pick<Resource, 'name' | 'description' | 'config'>,
): Values {
  const c = resource?.config || {};
  const text = (key: string, fallback = '') =>
    typeof c[key] === 'string' ? (c[key] as string) : fallback;
  return {
    name: resource?.name || '',
    description: resource?.description || '',
    content: text(
      'content',
      kind === 'skills'
        ? '---\nname: my-skill\ndescription: 描述这个 Skill 的用途\n---\n\n# 使用说明\n'
        : '',
    ),
    variables: ((c.variables || []) as string[]).join(', '),
    protocol: text('protocol', 'openai'),
    baseUrl: text('base_url'),
    model: text('model'),
    apiKey: '',
    platform: text('platform', 'codex'),
    command: text('command'),
    args: JSON.stringify(c.args || [], null, 2),
    env: JSON.stringify(c.env || {}, null, 2),
    headers: JSON.stringify(c.headers || {}, null, 2),
    transport: text('type', 'stdio'),
    url: text('url'),
    cwd: text('cwd'),
  };
}

function parse(text: string, label: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`${label}的 JSON 格式不正确`);
  }
}

export function configFromValues(kind: Kind, v: Values): Record<string, unknown> {
  if (kind === 'skills') return { content: v.content };
  if (kind === 'prompts')
    return { content: v.content, variables: v.variables.split(/[,，\s]+/).filter(Boolean) };
  if (kind === 'models')
    return { protocol: v.protocol, base_url: v.baseUrl, model: v.model, api_key: v.apiKey };
  if (kind === 'platforms')
    return {
      platform: v.platform,
      command: v.command,
      args: parse(v.args, '参数'),
      env: parse(v.env, '环境变量'),
      cwd: v.cwd || null,
    };
  return v.transport === 'stdio'
    ? {
        type: v.transport,
        command: v.command,
        args: parse(v.args, '参数'),
        env: parse(v.env, '环境变量'),
        cwd: v.cwd || null,
      }
    : { type: v.transport, url: v.url, headers: parse(v.headers, '请求头') };
}

export function makeDraft(
  kind: Kind,
  values: Values,
  resource?: Resource,
  clear: string[] = [],
  json?: string,
): Draft {
  return {
    name: values.name,
    description: values.description,
    config:
      json === undefined
        ? configFromValues(kind, values)
        : (parse(json, 'MCP 配置') as Draft['config']),
    revision: resource?.revision,
    clear_secrets: clear,
  };
}
