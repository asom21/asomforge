// 调用模型发现与草稿、已保存版本的真实文本测试接口。
import { request, responseError, type CheckResult } from './client';
import type { ModelConnection, ModelEntry } from '../features/configuration/models/values';

export interface ModelSource {
  config: ModelConnection;
  resource_id?: string;
  revision?: number;
  clear_api_key?: boolean;
}
export interface ProbeSelection {
  model_id: string;
  reasoning_effort?: string;
}

export async function discoverModels(
  source: ModelSource,
  signal: AbortSignal,
): Promise<ModelEntry[]> {
  const result = await request<{ models: ModelEntry[] }>('/api/model-connections/discover', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(source),
    signal,
  });
  return result.models;
}

export async function testModel(
  source: ModelSource | { resource_id: string; revision: number },
  selection: ProbeSelection,
  signal: AbortSignal,
  onEvent: (value: CheckResult) => void,
): Promise<void> {
  const draft = 'config' in source;
  const url = draft
    ? '/api/model-connections/test'
    : `/api/configurations/models/${source.resource_id}/test`;
  const body = draft ? { ...source, ...selection } : { revision: source.revision, ...selection };
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) throw await responseError(response);
  if (!response.body) throw new Error('模型测试没有返回事件流');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let completed = false;
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n');
      let boundary: number;
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        const event = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const line = event.split('\n').find((line) => line.startsWith('data: '));
        if (!line) continue;
        const result = JSON.parse(line.slice(6)) as CheckResult;
        if (signal.aborted) return;
        if (result.status !== 'running') completed = true;
        onEvent(result);
      }
      if (done) break;
    }
    if (!completed && !signal.aborted) throw new Error('测试连接已中断，请重试');
  } finally {
    reader.releaseLock();
  }
}
