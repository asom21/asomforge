// 展示可展开的模型目录条目、能力设置和草稿测试入口。
import { useState } from 'react';
import { ChevronDown, ChevronRight, FlaskConical, Plus, Trash2 } from 'lucide-react';
import type { ModelSource } from '../../../api/models';
import type { CheckReport } from '../../../api/client';
import { Status } from '../CheckPanel';
import { ModelProbe } from './ModelProbe';
import { ReasoningFields } from './ReasoningFields';
import { newModel, type ConnectionDraft, type ModelDraft, type ModelEntry } from './values';

interface Props {
  draft: ConnectionDraft;
  onChange: (draft: ConnectionDraft) => void;
  getSource: () => ModelSource;
  onBusyChange: (busy: boolean) => void;
  checks?: Record<string, CheckReport>;
  unchanged?: boolean;
}
export function ModelCatalogEditor({
  draft,
  onChange,
  getSource,
  onBusyChange,
  checks = {},
  unchanged = false,
}: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [testing, setTesting] = useState<string | null>(null);
  const patch = (key: string, value: Partial<ModelDraft>) =>
    onChange({
      ...draft,
      models: draft.models.map((m) => (m.key === key ? { ...m, ...value } : m)),
    });
  const signature = JSON.stringify(draft);
  return (
    <div className="model-catalog">
      {draft.models.map((model, index) => {
        const open = expanded.has(model.key);
        const probeModel: ModelEntry = {
          id: model.id.trim(),
          name: model.name,
          input_modalities: model.inputModalities,
          ...(Array.isArray(model.reasoning)
            ? {
                reasoning_efforts: Object.fromEntries(
                  model.reasoning.map((e) => [e.level, e.value || null]),
                ),
              }
            : {}),
        };
        return (
          <article className="model-card" key={model.key}>
            <div className="model-card-top">
              <span className="model-position">{String(index + 1).padStart(2, '0')}</span>
              <label className="model-identity">
                <span>模型 ID</span>
                <input
                  aria-label={`模型 ID ${index + 1}`}
                  value={model.id}
                  onChange={(e) => patch(model.key, { id: e.target.value })}
                  placeholder="例如 gpt-4.1"
                />
              </label>
              <label className="model-identity">
                <span>显示名称</span>
                <input
                  aria-label={`模型显示名称 ${index + 1}`}
                  value={model.name}
                  onChange={(e) => patch(model.key, { name: e.target.value })}
                  placeholder="可选"
                />
              </label>
              <button
                type="button"
                className="icon-button"
                aria-label={`展开模型 ${index + 1} 的高级配置`}
                aria-expanded={open}
                onClick={() =>
                  setExpanded((current) => {
                    const next = new Set(current);
                    if (!next.delete(model.key)) next.add(model.key);
                    return next;
                  })
                }
              >
                {open ? <ChevronDown size={17} /> : <ChevronRight size={17} />}
              </button>
              <button
                type="button"
                className="icon-button delete-button"
                aria-label={`删除模型 ${index + 1}`}
                onClick={() => {
                  const models = draft.models.filter((m) => m.key !== model.key);
                  if (testing === model.key) setTesting(null);
                  onChange({
                    ...draft,
                    models,
                    defaultModelKey:
                      draft.defaultModelKey === model.key
                        ? (models[0]?.key ?? '')
                        : draft.defaultModelKey,
                  });
                }}
              >
                <Trash2 size={16} />
              </button>
            </div>
            <div className="model-card-meta">
              <label className="model-default">
                <input
                  type="radio"
                  name="default-model"
                  checked={draft.defaultModelKey === model.key}
                  onChange={() => onChange({ ...draft, defaultModelKey: model.key })}
                />
                默认模型
              </label>
              <span className="model-card-check">
                {checks[model.id]?.details?.mode === 'generation' ? (
                  unchanged ? (
                    <Status check={checks[model.id]} />
                  ) : (
                    <span className="muted">结果已过期</span>
                  )
                ) : (
                  <span className="muted">尚未测试</span>
                )}
              </span>
              <button
                type="button"
                className="text-button"
                aria-expanded={testing === model.key}
                onClick={() => setTesting(testing === model.key ? null : model.key)}
              >
                <FlaskConical size={14} />
                {testing === model.key ? '收起测试' : '测试连接'}
              </button>
            </div>
            {open && (
              <div className="model-advanced">
                <div className="model-two-columns">
                  <label className="field">
                    <span>上下文窗口</span>
                    <input
                      value={model.contextWindow}
                      aria-label={`上下文窗口 ${index + 1}`}
                      placeholder="未声明，如 128K"
                      onChange={(e) => patch(model.key, { contextWindow: e.target.value })}
                    />
                  </label>
                  <label className="field">
                    <span>最大输出 token</span>
                    <input
                      value={model.maxOutputTokens}
                      aria-label={`最大输出 token ${index + 1}`}
                      placeholder="未声明，如 32K"
                      onChange={(e) => patch(model.key, { maxOutputTokens: e.target.value })}
                    />
                  </label>
                </div>
                <fieldset className="model-modalities">
                  <legend>输入类型</legend>
                  {(['text', 'image'] as const).map((input) => (
                    <label key={input}>
                      <input
                        type="checkbox"
                        checked={model.inputModalities.includes(input)}
                        onChange={(e) =>
                          patch(model.key, {
                            inputModalities: e.target.checked
                              ? [...model.inputModalities, input]
                              : model.inputModalities.filter((i) => i !== input),
                          })
                        }
                      />
                      {input === 'text' ? '文本' : '图片'}
                    </label>
                  ))}
                </fieldset>
                <ReasoningFields
                  model={model}
                  anthropic={draft.protocol === 'anthropic-messages'}
                  onChange={(reasoning) => patch(model.key, { reasoning })}
                />
              </div>
            )}
            {testing === model.key && (
              <ModelProbe
                model={probeModel}
                signature={signature}
                getSource={getSource}
                draft
                onBusyChange={onBusyChange}
              />
            )}
          </article>
        );
      })}
      <button
        type="button"
        className="add-model"
        onClick={() => {
          const model = newModel();
          onChange({
            ...draft,
            models: [...draft.models, model],
            defaultModelKey: draft.defaultModelKey || model.key,
          });
        }}
      >
        <Plus size={16} />
        添加模型
      </button>
    </div>
  );
}
