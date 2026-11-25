// 编辑每个模型可用的推理档位及其 API 参数映射。
import { Plus, Trash2 } from 'lucide-react';
import { effortLevels, type ModelDraft, type EffortLevel } from './values';

export function ReasoningFields({
  model,
  anthropic,
  onChange,
}: {
  model: ModelDraft;
  anthropic: boolean;
  onChange: (value: ModelDraft['reasoning']) => void;
}) {
  const entries = Array.isArray(model.reasoning) ? model.reasoning : [];
  if (anthropic)
    return entries.length ? (
      <div className="model-warning" role="alert">
        <p>Anthropic 的思考参数需单独适配，请移除当前通用档位映射后保存。</p>
        <button type="button" onClick={() => onChange(false)}>
          移除推理档位
        </button>
      </div>
    ) : null;
  return (
    <div className="reasoning-fields">
      <div className="model-section-heading">
        <span>推理档位</span>
        <button
          type="button"
          className="enable-toggle"
          role="switch"
          aria-label={`启用推理档位 ${model.id || '新模型'}`}
          aria-checked={Array.isArray(model.reasoning)}
          onClick={() =>
            onChange(
              Array.isArray(model.reasoning)
                ? false
                : [
                    { level: 'low', value: 'low' },
                    { level: 'medium', value: 'medium' },
                    { level: 'high', value: 'high' },
                  ],
            )
          }
        >
          <span className="toggle-track" aria-hidden="true">
            <span />
          </span>
        </button>
      </div>
      {Array.isArray(model.reasoning) && (
        <>
          <div className="reasoning-labels" aria-hidden="true">
            <span>档位</span>
            <span>API 参数值</span>
          </div>
          {entries.map((entry, index) => (
            <div className="reasoning-row" key={index}>
              <select
                aria-label={`推理档位 ${index + 1}`}
                value={entry.level}
                onChange={(e) => {
                  const level = e.target.value as EffortLevel;
                  onChange(
                    entries.map((item, at) =>
                      at === index
                        ? {
                            level,
                            value:
                              item.value === item.level
                                ? level === 'off'
                                  ? ''
                                  : level
                                : item.value,
                          }
                        : item,
                    ),
                  );
                }}
              >
                {effortLevels
                  .filter(
                    (level) =>
                      level === entry.level || !entries.some((item) => item.level === level),
                  )
                  .map((level) => (
                    <option value={level} key={level}>
                      {level}
                    </option>
                  ))}
              </select>
              <input
                aria-label={`档位 ${entry.level} API 参数值`}
                value={entry.value}
                placeholder={entry.level === 'off' ? '留空不发送推理参数' : entry.level}
                onChange={(e) =>
                  onChange(
                    entries.map((item, at) =>
                      at === index ? { ...item, value: e.target.value } : item,
                    ),
                  )
                }
              />
              <button
                type="button"
                className="icon-button delete-button"
                aria-label={`删除推理档位 ${entry.level}`}
                onClick={() => onChange(entries.filter((_, at) => at !== index))}
              >
                <Trash2 size={15} />
              </button>
            </div>
          ))}
          <button
            type="button"
            className="text-button"
            disabled={entries.length >= effortLevels.length}
            onClick={() => {
              const level = effortLevels.find(
                (level) => !entries.some((item) => item.level === level),
              );
              if (level) onChange([...entries, { level, value: level === 'off' ? '' : level }]);
            }}
          >
            <Plus size={14} />
            添加档位
          </button>
          <p className="helper-note">
            只配置提供商明确支持的档位。off 留空表示不发送参数，不保证端点关闭思考。
          </p>
        </>
      )}
    </div>
  );
}
