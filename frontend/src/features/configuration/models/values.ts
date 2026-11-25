// 转换模型连接的嵌套表单与 API 配置，校验容量、默认选择和推理映射。
import type { Resource } from '../../../api/client';
import type { components } from '../../../api/schema';

export type Protocol = 'openai-chat-completions' | 'openai-responses' | 'anthropic-messages';
export const protocols: Record<Protocol, string> = {
  'openai-chat-completions': 'OpenAI Chat Completions',
  'openai-responses': 'OpenAI Responses',
  'anthropic-messages': 'Anthropic Messages',
};
export const effortLevels = ['off', 'minimal', 'low', 'medium', 'high', 'xhigh'] as const;
export type EffortLevel = (typeof effortLevels)[number];
type WireModelEntry = components['schemas']['ModelEntry'];
export type ModelEntry = Pick<WireModelEntry, 'id'> & Partial<Omit<WireModelEntry, 'id'>>;
export type ModelConnection = Omit<
  components['schemas']['ModelConfig'],
  'models' | 'output_token_field'
> & {
  models: ModelEntry[];
  output_token_field?: 'max_completion_tokens' | 'max_tokens';
};
export interface ModelDraft {
  key: string;
  id: string;
  name: string;
  contextWindow: string;
  maxOutputTokens: string;
  inputModalities: ('text' | 'image')[];
  reasoning: null | false | { level: EffortLevel; value: string }[];
}
export interface ConnectionDraft {
  name: string;
  description: string;
  protocol: Protocol;
  baseUrl: string;
  apiKey: string;
  clearApiKey: boolean;
  outputTokenField: 'max_completion_tokens' | 'max_tokens';
  models: ModelDraft[];
  defaultModelKey: string;
}

export function parseCapacity(value: string): number | undefined {
  const text = value.trim().toUpperCase();
  if (!text) return undefined;
  if (!/^\d+(?:\.\d+)?[KM]?$/.test(text)) throw new Error('容量请输入正整数或 K/M 简写');
  const count = parseFloat(text) * (text.endsWith('M') ? 1000000 : text.endsWith('K') ? 1000 : 1);
  if (!Number.isSafeInteger(count) || count <= 0) throw new Error('容量必须为正整数 token 数');
  return count;
}

export function formatCapacity(value?: number | null): string {
  if (!value) return '';
  if (value % 1000000 === 0) return `${value / 1000000}M`;
  if (value % 1000 === 0) return `${value / 1000}K`;
  return String(value);
}

export function newModel(entry: ModelEntry = { id: '' }): ModelDraft {
  return {
    key: crypto.randomUUID(),
    id: entry.id,
    name: entry.name ?? '',
    contextWindow: formatCapacity(entry.context_window),
    maxOutputTokens: formatCapacity(entry.max_output_tokens),
    inputModalities: entry.input_modalities ? [...entry.input_modalities] : ['text'],
    reasoning:
      entry.reasoning_efforts === false
        ? false
        : entry.reasoning_efforts
          ? Object.entries(entry.reasoning_efforts).map(([level, value]) => ({
              level: level as EffortLevel,
              value: value ?? '',
            }))
          : null,
  };
}

export function initialConnection(
  resource?: Pick<Resource, 'name' | 'description' | 'config'>,
): ConnectionDraft {
  const config = resource?.config ?? {};
  const rawProtocol = String(config.protocol ?? 'openai-chat-completions');
  const protocol =
    rawProtocol === 'openai'
      ? 'openai-chat-completions'
      : rawProtocol === 'anthropic'
        ? 'anthropic-messages'
        : (rawProtocol as Protocol);
  const entries = Array.isArray(config.models)
    ? (config.models as ModelEntry[])
    : config.model
      ? [{ id: String(config.model) }]
      : [];
  const models = entries.length ? entries.map(newModel) : [newModel()];
  return {
    name: resource?.name ?? '',
    description: resource?.description ?? '',
    protocol,
    baseUrl: String(config.base_url ?? ''),
    apiKey: '',
    clearApiKey: false,
    outputTokenField:
      config.output_token_field === 'max_tokens' ? 'max_tokens' : 'max_completion_tokens',
    models,
    defaultModelKey: models.find((m) => m.id === config.default_model_id)?.key ?? models[0].key,
  };
}

function baseConfig(draft: ConnectionDraft): ModelConnection {
  let url: URL;
  try {
    url = new URL(draft.baseUrl.trim());
  } catch {
    throw new Error('请填写有效的 API 地址');
  }
  if (
    !['http:', 'https:'].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash
  ) {
    throw new Error('API 地址需为不含账号、查询参数和片段的 HTTP/HTTPS 协议根地址');
  }
  return {
    protocol: draft.protocol,
    base_url: draft.baseUrl.trim(),
    api_key: draft.clearApiKey ? '' : draft.apiKey.trim(),
    ...(draft.protocol === 'openai-chat-completions'
      ? { output_token_field: draft.outputTokenField }
      : {}),
    models: [],
    default_model_id: '',
  };
}

export function discoveryConfig(draft: ConnectionDraft): ModelConnection {
  return baseConfig(draft);
}

export function connectionConfig(draft: ConnectionDraft): ModelConnection {
  const config = baseConfig(draft);
  if (!draft.models.length) throw new Error('请至少添加一个模型');
  const seen = new Set<string>();
  config.models = draft.models.map((model, index) => {
    const label = `模型 ${index + 1}`;
    const id = model.id.trim();
    if (!id) throw new Error(`${label}：请填写模型 ID`);
    if (seen.has(id)) throw new Error(`模型 ID 重复：${id}`);
    seen.add(id);
    const context = parseCapacity(model.contextWindow);
    const output = parseCapacity(model.maxOutputTokens);
    if (context && output && output > context)
      throw new Error(`${label}：最大输出不能超过上下文窗口`);
    if (!model.inputModalities.length) throw new Error(`${label}：至少选择一种输入类型`);
    let reasoning: ModelEntry['reasoning_efforts'];
    if (Array.isArray(model.reasoning)) {
      if (draft.protocol === 'anthropic-messages')
        throw new Error('Anthropic 暂不支持此推理映射，请先关闭已有档位');
      if (!model.reasoning.some((e) => e.level !== 'off'))
        throw new Error(`${label}：请添加至少一个非 off 档位`);
      const levels = new Set<string>();
      reasoning = {};
      for (const effort of model.reasoning) {
        if (levels.has(effort.level)) throw new Error(`${label}：推理档位重复`);
        levels.add(effort.level);
        const value = effort.value.trim();
        if (effort.level !== 'off' && !value)
          throw new Error(`${label}：${effort.level} 需要 API 参数值`);
        reasoning[effort.level] = value || null;
      }
    } else if (model.reasoning === false) reasoning = false;
    return {
      id,
      ...(model.name.trim() ? { name: model.name.trim() } : {}),
      ...(context ? { context_window: context } : {}),
      ...(output ? { max_output_tokens: output } : {}),
      input_modalities: model.inputModalities,
      ...(reasoning !== undefined ? { reasoning_efforts: reasoning } : {}),
    };
  });
  const selected = draft.models.find((m) => m.key === draft.defaultModelKey);
  if (!selected) throw new Error('请选择有效的默认模型');
  config.default_model_id = selected.id.trim();
  return config;
}

export function mergeCandidates(draft: ConnectionDraft, candidates: ModelEntry[]): ConnectionDraft {
  const known = new Set(draft.models.map((m) => m.id.trim()));
  const added: ModelDraft[] = [];
  for (const candidate of candidates) {
    if (!known.has(candidate.id)) {
      known.add(candidate.id);
      added.push(newModel(candidate));
    }
  }
  const models = [
    ...draft.models.filter(
      (m) => m.id.trim() || m.name.trim() || m.contextWindow || m.maxOutputTokens,
    ),
    ...added,
  ];
  return {
    ...draft,
    models,
    defaultModelKey: models.some((m) => m.key === draft.defaultModelKey)
      ? draft.defaultModelKey
      : (models[0]?.key ?? ''),
  };
}
