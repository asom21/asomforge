// 展示单模型的真实连通性测试、取消操作与配置变化后的结果有效期。
import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, CircleAlert, LoaderCircle, Play, Square } from 'lucide-react';
import { errorMessage, type CheckReport, type CheckResult } from '../../../api/client';
import { testModel, type ModelSource } from '../../../api/models';
import type { ModelEntry } from './values';

export const connectionPrompt = '请只回复：连接成功。不要执行命令或修改文件。';
type Source = ModelSource | { resource_id: string; revision: number };
interface Props {
  model: ModelEntry;
  signature: string;
  getSource: () => Source;
  savedResult?: CheckReport | null;
  draft?: boolean;
  onCompleted?: () => void;
  onBusyChange?: (busy: boolean) => void;
}

export function ModelProbe({
  model,
  signature,
  getSource,
  savedResult,
  draft = false,
  onCompleted,
  onBusyChange,
}: Props) {
  const levels =
    model.reasoning_efforts && typeof model.reasoning_efforts === 'object'
      ? Object.keys(model.reasoning_efforts)
      : [];
  const savedEffort =
    typeof savedResult?.details?.reasoning_effort === 'string' &&
    levels.includes(savedResult.details.reasoning_effort)
      ? savedResult.details.reasoning_effort
      : '';
  const [effort, setEffort] = useState(savedEffort);
  const [result, setResult] = useState<{ value: CheckResult; signature: string } | null>(
    savedResult?.details?.mode === 'generation'
      ? { value: savedResult, signature: signature + '|' + savedEffort }
      : null,
  );
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null);
  const currentSignature = signature + '|' + effort;
  const activeSignature = useRef(currentSignature);
  activeSignature.current = currentSignature;
  const busyCallback = useRef(onBusyChange);
  busyCallback.current = onBusyChange;
  useEffect(
    () => () => {
      controller.current?.abort();
      busyCallback.current?.(false);
    },
    [],
  );
  const stale = result !== null && result.signature !== currentSignature;
  const levelsSignature = levels.join('|');
  useEffect(() => {
    if (effort && !levels.includes(effort)) setEffort('');
  }, [effort, levelsSignature]);

  async function run() {
    if (controller.current) return;
    let source: Source;
    try {
      source = getSource();
      if (!model.id.trim()) throw new Error('请先填写模型 ID');
      if (!model.input_modalities?.includes('text'))
        throw new Error('当前测试需要模型支持文本输入');
    } catch (err) {
      setError(errorMessage(err));
      return;
    }
    const request = new AbortController();
    const sentSignature = currentSignature;
    controller.current = request;
    setRunning(true);
    busyCallback.current?.(true);
    setError('');
    setResult(null);
    try {
      await testModel(
        source,
        { model_id: model.id.trim(), ...(effort ? { reasoning_effort: effort } : {}) },
        request.signal,
        (value) => {
          if (request.signal.aborted) return;
          setResult({ value, signature: sentSignature });
          if (value.status !== 'running') onCompleted?.();
        },
      );
    } catch (err) {
      if (request.signal.aborted) {
        setError('测试已取消，远端可能已经处理请求并产生少量费用。');
        setResult(null);
      } else setError(errorMessage(err));
    } finally {
      controller.current = null;
      setRunning(false);
      busyCallback.current?.(false);
      if (sentSignature !== activeSignature.current)
        setError('配置已变化，本次结果已过期，请重新测试。');
    }
  }
  const value = result?.value;
  const preview =
    value && typeof value.details?.response_preview === 'string'
      ? value.details.response_preview
      : '';
  const latency =
    value && typeof value.details?.latency_ms === 'number' ? value.details.latency_ms : null;
  return (
    <section className="model-probe" aria-label={`${model.name || model.id || '模型'}连接测试`}>
      <div className="model-probe-heading">
        <strong>文本连通性测试</strong>
        <span className="tag">{draft ? '当前草稿 · 不保存结果' : '已保存版本'}</span>
      </div>
      <p className="probe-prompt">{connectionPrompt}</p>
      <p className="helper-note">
        将发送一次真实请求，最多输出 1024 token，可能产生少量费用。仅验证文本响应。
      </p>
      <div className="model-probe-actions">
        <label className="probe-effort">
          <span>推理档位</span>
          <select value={effort} disabled={running} onChange={(e) => setEffort(e.target.value)}>
            <option value="">接口默认</option>
            {levels.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
        </label>
        {running ? (
          <button type="button" onClick={() => controller.current?.abort()}>
            <Square size={14} />
            取消测试
          </button>
        ) : (
          <button type="button" className="primary" onClick={() => void run()}>
            <Play size={14} />
            {value ? '重新测试' : '开始测试'}
          </button>
        )}
      </div>
      {value && (
        <div className={`probe-result ${stale ? 'stale' : value.status}`} role="status">
          {running ? (
            <LoaderCircle size={17} className="spin" />
          ) : value.status === 'passed' && !stale ? (
            <CheckCircle2 size={17} />
          ) : (
            <CircleAlert size={17} />
          )}
          <div>
            <strong>{stale ? '配置已变化，结果已过期' : value.message}</strong>
            {!stale && preview && <p className="probe-response">{preview}</p>}
            {value.status !== 'running' && (
              <small>
                {latency !== null && `${Math.round(latency)} ms · `}
                {value.checked_at && new Date(value.checked_at).toLocaleString('zh-CN')}
                {value.details?.persisted === false && !draft ? ' · 配置已更新，结果未登记' : ''}
              </small>
            )}
          </div>
        </div>
      )}
      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}
    </section>
  );
}
