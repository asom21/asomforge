// 编辑模型连接和目录，管理发现候选、凭据清除及未保存提醒。
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Download, LoaderCircle, Save, X } from 'lucide-react';
import { api, errorMessage, type Resource } from '../../../api/client';
import { discoverModels, type ModelSource } from '../../../api/models';
import { Modal } from '../../../components/Modal';
import { Field } from '../forms/ConfigurationFields';
import { ModelCatalogEditor } from './ModelCatalogEditor';
import {
  connectionConfig,
  discoveryConfig,
  initialConnection,
  mergeCandidates,
  protocols,
  type ModelEntry,
  type Protocol,
} from './values';

export function ModelConnectionEditor({
  resource,
  onClose,
  onSaved,
}: {
  resource?: Resource;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState(() => initialConnection(resource));
  const [baseline] = useState(() => JSON.stringify(draft));
  const [saving, setSaving] = useState(false);
  const [probeBusy, setProbeBusy] = useState(false);
  const [discoverBusy, setDiscoverBusy] = useState(false);
  const [error, setError] = useState('');
  const [discoveryError, setDiscoveryError] = useState('');
  const [candidates, setCandidates] = useState<ModelEntry[] | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [candidateQuery, setCandidateQuery] = useState('');
  const discoveryRequest = useRef<AbortController | null>(null);
  const dirty = JSON.stringify(draft) !== baseline;
  useEffect(() => {
    const guard = (e: BeforeUnloadEvent) => {
      if (dirty) e.preventDefault();
    };
    window.addEventListener('beforeunload', guard);
    return () => window.removeEventListener('beforeunload', guard);
  }, [dirty]);
  useEffect(() => {
    discoveryRequest.current?.abort();
    setCandidates(null);
    setDiscoveryError('');
  }, [draft.baseUrl, draft.protocol, draft.apiKey, draft.clearApiKey]);
  useEffect(() => () => discoveryRequest.current?.abort(), []);
  function close() {
    if (saving) return;
    if (dirty && !window.confirm('放弃未保存的修改？')) return;
    discoveryRequest.current?.abort();
    onClose();
  }
  function source(discover = false): ModelSource {
    return {
      config: discover ? discoveryConfig(draft) : connectionConfig(draft),
      ...(resource ? { resource_id: resource.id, revision: resource.revision } : {}),
      clear_api_key: draft.clearApiKey,
    };
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    setError('');
    try {
      if (!draft.name.trim()) throw new Error('请填写连接名称');
      const config = connectionConfig(draft);
      setSaving(true);
      await api.save(
        'models',
        {
          name: draft.name.trim(),
          description: draft.description,
          config: { ...config },
          revision: resource?.revision,
          clear_secrets: draft.clearApiKey ? ['api_key'] : [],
        },
        resource?.id,
      );
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }
  async function discover() {
    let body: ModelSource;
    try {
      body = source(true);
    } catch (err) {
      setDiscoveryError(errorMessage(err));
      return;
    }
    const request = new AbortController();
    discoveryRequest.current?.abort();
    discoveryRequest.current = request;
    setDiscoverBusy(true);
    setDiscoveryError('');
    setCandidates(null);
    try {
      const found = await discoverModels(body, request.signal);
      if (request.signal.aborted) return;
      setCandidates(found);
      setCandidateQuery('');
      const known = new Set(draft.models.map((m) => m.id.trim()));
      setPicked(new Set(found.filter((m) => !known.has(m.id)).map((m) => m.id)));
      if (!found.length) setDiscoveryError('接口未返回可用模型，可以继续手动添加。');
    } catch (err) {
      if (!request.signal.aborted)
        setDiscoveryError(errorMessage(err) + '；可以继续手动添加并测试模型。');
    } finally {
      if (discoveryRequest.current === request) {
        setDiscoverBusy(false);
        discoveryRequest.current = null;
      }
    }
  }
  const known = new Set(draft.models.map((m) => m.id.trim()));
  return (
    <Modal
      className="editor-dialog model-connection-dialog"
      label={resource ? '编辑模型连接' : '新建模型连接'}
      onClose={close}
    >
      <header className="dialog-header">
        <div>
          <span className="muted">配置中心 / 大模型</span>
          <h2>{resource ? '编辑模型连接' : '新建模型连接'}</h2>
        </div>
        <button className="icon-button" onClick={close} disabled={saving} aria-label="关闭编辑">
          <X size={20} />
        </button>
      </header>
      <form onSubmit={save}>
        <div className="dialog-body">
          <div className="model-two-columns">
            <Field label="连接名称">
              <input
                value={draft.name}
                maxLength={160}
                required
                autoFocus
                placeholder="例如 我的模型网关"
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              />
            </Field>
            <Field label="说明（可选）">
              <input
                value={draft.description}
                placeholder="记录连接的用途"
                onChange={(e) => setDraft({ ...draft, description: e.target.value })}
              />
            </Field>
          </div>
          <Field label="API 地址">
            <input
              type="url"
              value={draft.baseUrl}
              placeholder="https://api.example.com/v1"
              required
              onChange={(e) => setDraft({ ...draft, baseUrl: e.target.value })}
            />
          </Field>
          <div className="model-two-columns">
            <Field label="API 协议">
              <select
                value={draft.protocol}
                onChange={(e) => setDraft({ ...draft, protocol: e.target.value as Protocol })}
              >
                {Object.entries(protocols).map(([value, label]) => (
                  <option value={value} key={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="API Key">
              <input
                type="password"
                autoComplete="off"
                value={draft.apiKey}
                disabled={draft.clearApiKey}
                placeholder={
                  resource?.secret_fields.includes('api_key')
                    ? '已保存 · 留空保留'
                    : '可选：填写 API Key'
                }
                onChange={(e) => setDraft({ ...draft, apiKey: e.target.value })}
              />
            </Field>
          </div>
          {resource?.secret_fields.includes('api_key') && (
            <label className="model-clear-key">
              <input
                type="checkbox"
                checked={draft.clearApiKey}
                onChange={(e) => setDraft({ ...draft, clearApiKey: e.target.checked })}
              />
              清除已保存的 API Key（测试时也不使用旧密钥）
            </label>
          )}
          {draft.protocol === 'openai-chat-completions' && (
            <details className="model-compat">
              <summary>接口兼容设置</summary>
              <Field label="输出 token 上限字段">
                <select
                  value={draft.outputTokenField}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      outputTokenField: e.target.value as typeof draft.outputTokenField,
                    })
                  }
                >
                  <option value="max_completion_tokens">max_completion_tokens（默认）</option>
                  <option value="max_tokens">max_tokens（旧接口兼容）</option>
                </select>
              </Field>
            </details>
          )}
          <div className="section-label model-catalog-heading">
            <div>
              <h3>
                模型目录 <span className="count-badge">{draft.models.length}</span>
              </h3>
              <p className="muted">一份连接可配置多个模型，展开后设置能力。</p>
            </div>
            <button
              type="button"
              disabled={discoverBusy || probeBusy}
              onClick={() => void discover()}
            >
              {discoverBusy ? <LoaderCircle className="spin" size={15} /> : <Download size={15} />}
              {discoverBusy ? '正在获取…' : '获取可用模型'}
            </button>
          </div>
          {discoverBusy && (
            <button
              type="button"
              className="text-button"
              onClick={() => discoveryRequest.current?.abort()}
            >
              取消获取
            </button>
          )}
          {discoveryError && (
            <div className="model-warning" role="alert">
              {discoveryError}
            </div>
          )}
          {candidates && candidates.length > 0 && (
            <section className="model-candidates" aria-label="选择发现的模型">
              <div className="model-section-heading">
                <strong>选择要添加的模型</strong>
                <button
                  type="button"
                  className="icon-button"
                  aria-label="关闭候选列表"
                  onClick={() => setCandidates(null)}
                >
                  <X size={16} />
                </button>
              </div>
              <input
                aria-label="搜索可用模型"
                placeholder="搜索模型 ID 或名称"
                value={candidateQuery}
                onChange={(e) => setCandidateQuery(e.target.value)}
              />
              <div className="model-candidate-list">
                {candidates
                  .filter((m) =>
                    `${m.id} ${m.name ?? ''}`.toLowerCase().includes(candidateQuery.toLowerCase()),
                  )
                  .map((m) => (
                    <label key={m.id}>
                      <input
                        type="checkbox"
                        disabled={known.has(m.id)}
                        checked={known.has(m.id) || picked.has(m.id)}
                        onChange={(e) =>
                          setPicked((current) => {
                            const next = new Set(current);
                            if (e.target.checked) next.add(m.id);
                            else next.delete(m.id);
                            return next;
                          })
                        }
                      />
                      <span>
                        <strong>{m.id}</strong>
                        <small>
                          {known.has(m.id)
                            ? '已添加'
                            : m.name && m.name !== m.id
                              ? m.name
                              : '可添加'}
                        </small>
                      </span>
                    </label>
                  ))}
              </div>
              <button
                type="button"
                className="primary"
                disabled={!picked.size}
                onClick={() => {
                  setDraft((current) =>
                    mergeCandidates(
                      current,
                      candidates.filter((m) => picked.has(m.id)),
                    ),
                  );
                  setCandidates(null);
                }}
              >
                添加所选模型（{picked.size}）
              </button>
            </section>
          )}
          <ModelCatalogEditor
            draft={draft}
            onChange={setDraft}
            getSource={() => source()}
            onBusyChange={setProbeBusy}
            checks={resource?.model_checks}
            unchanged={!dirty}
          />
          {error && (
            <div className="error-box" role="alert">
              {error}
            </div>
          )}
        </div>
        <footer className="dialog-footer">
          <span className="muted">{dirty ? '有未保存的修改' : '连接与模型保存在本机'}</span>
          <div>
            <button type="button" onClick={close} disabled={saving}>
              取消
            </button>
            <button
              className="primary"
              type="submit"
              disabled={saving || probeBusy || discoverBusy}
            >
              <Save size={16} />
              {saving ? '保存中…' : '保存配置'}
            </button>
          </div>
        </footer>
      </form>
    </Modal>
  );
}
