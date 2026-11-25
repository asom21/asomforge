// 统一调用配置接口、处理错误并读取检查事件流。
import type { components } from './schema';

export type Resource = components['schemas']['Resource'];
export type Draft = components['schemas']['Draft'];
export type Kind = Resource['kind'];
export type Category = Kind | 'tools';
export type Catalog = components['schemas']['Catalog'];
export type CheckReport = components['schemas']['CheckResult'];
export type CheckResult =
  | CheckReport
  | (Omit<Partial<CheckReport>, 'status'> & {
      status: 'running';
      message: string;
    });
export type ImportPreview = components['schemas']['ImportPreview'];
export type ImportResults = components['schemas']['ImportResults'];

export async function responseError(response: Response): Promise<Error> {
  try {
    const body = await response.json();
    const message = Array.isArray(body.detail)
      ? body.detail
          .map((item: { loc: string[]; msg: string }) => `${item.loc.join('.')}：${item.msg}`)
          .join('；')
      : body.detail;
    return new Error(typeof message === 'string' ? message : `请求失败 (${response.status})`);
  } catch {
    return new Error(`服务返回错误 (${response.status})`);
  }
}

export async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new Error('无法连接本地服务，请确认后端已启动');
  }
  if (!response.ok) throw await responseError(response);
  return response.status === 204 ? (undefined as T) : response.json();
}

const json = (body: unknown, method = 'POST'): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});
const path = (kind: Kind, id?: string) => `/api/configurations/${kind}${id ? `/${id}` : ''}`;

export const api = {
  catalog: () => request<Catalog>('/api/catalog'),
  list: (kind: Kind, signal?: AbortSignal) => request<Resource[]>(path(kind), { signal }),
  save: (kind: Kind, draft: Draft, id?: string) =>
    request<Resource>(path(kind, id), json(draft, id ? 'PUT' : 'POST')),
  setEnabled: (resource: Resource, enabled: boolean) =>
    request<Resource>(
      path(resource.kind, resource.id),
      json(
        {
          enabled,
          revision: resource.revision,
        } satisfies components['schemas']['EnabledChange'],
        'PATCH',
      ),
    ),
  delete: (resource: Resource) =>
    request<void>(path(resource.kind, resource.id), { method: 'DELETE' }),
  files: (id: string) => request<{ path: string; size: number }[]>(`${path('skills', id)}/files`),
  import: <T>(
    kind: Kind,
    action: 'preview' | 'commit',
    body: FormData | { text: string; policy: string },
  ) =>
    request<T>(
      `/api/imports/${kind}/${action}`,
      body instanceof FormData ? { method: 'POST', body } : json(body),
    ),
  async check(resource: Resource, signal: AbortSignal, onEvent: (value: CheckResult) => void) {
    const response = await fetch(`${path(resource.kind, resource.id)}/check`, {
      method: 'POST',
      signal,
    });
    if (!response.ok) throw await responseError(response);
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let boundary: number;
        while ((boundary = buffer.indexOf('\n\n')) >= 0) {
          const event = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          if (event.startsWith('data: ')) onEvent(JSON.parse(event.slice(6)) as CheckResult);
        }
      }
    } finally {
      reader.releaseLock();
    }
  },
};

export const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : '操作失败，请重试';
