// 展示配置检查结果，支持启动和取消本次检查。
import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, CircleAlert, LoaderCircle, Play, X } from 'lucide-react';
import { api, errorMessage, type CheckResult, type Resource } from '../../api/client';
import { Modal } from '../../components/Modal';

export function Status({ check }: { check?: { status?: string } | null }) {
  const status = check?.status;
  return (
    <span className={`status ${status || 'idle'}`}>
      <i />
      {status === 'passed'
        ? '检查通过'
        : status === 'limited'
          ? '部分确认'
          : status === 'failed'
            ? '检查未通过'
            : '尚未检查'}
    </span>
  );
}

export function CheckPanel({
  resource,
  onClose,
  onUpdated,
}: {
  resource: Resource;
  onClose: () => void;
  onUpdated: () => void;
}) {
  const [result, setResult] = useState<CheckResult | null>(resource.last_check ?? null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function run() {
    const request = new AbortController();
    controller.current = request;
    setRunning(true);
    setError('');
    setResult(null);
    try {
      await api.check(resource, request.signal, setResult);
      onUpdated();
    } catch (error) {
      setError(request.signal.aborted ? '检查已取消，本次结果不保存。' : errorMessage(error));
      setResult(null);
    } finally {
      setRunning(false);
      controller.current = null;
    }
  }
  return (
    <Modal className="check-dialog" label="配置检查" onClose={onClose}>
      <header className="dialog-header">
        <div>
          <span className="muted">配置检查</span>
          <h2>{resource.name}</h2>
        </div>
        <button className="icon-button" onClick={onClose} aria-label="关闭检查">
          <X size={20} />
        </button>
      </header>
      <div className="dialog-body">
        <div className={`check-emblem ${running ? 'running' : result?.status || ''}`}>
          {running ? (
            <LoaderCircle className="spin" size={28} />
          ) : result?.status === 'passed' ? (
            <CheckCircle2 size={28} />
          ) : (
            <CircleAlert size={28} />
          )}
        </div>
        <h3 className="check-message">
          {result?.message || (error ? '本次检查未完成' : '准备好后，开始一次独立检查')}
        </h3>
        <p className="muted check-explanation">
          {resource.kind === 'mcp'
            ? '建立协议连接并发现能力，不调用业务工具。'
            : resource.kind === 'models'
              ? '读取模型列表，不发送生成请求。'
              : resource.kind === 'platforms'
                ? '读取版本与平台支持的认证状态，不启动 Agent 任务。'
                : '检查已保存内容的结构与完整性。'}
        </p>
        {result?.checked_at && (
          <dl className="check-meta">
            <dt>配置版本</dt>
            <dd>r{result.revision}</dd>
            <dt>检查时间</dt>
            <dd>{new Date(result.checked_at).toLocaleString('zh-CN')}</dd>
            <dt>工作目录</dt>
            <dd>
              <code>{result.cwd}</code>
            </dd>
          </dl>
        )}
        {result?.details && (
          <details className="result-details">
            <summary>检查详情</summary>
            <pre>{JSON.stringify(result.details, null, 2)}</pre>
          </details>
        )}
        {error && (
          <div className="error-box" role="alert">
            {error}
          </div>
        )}
      </div>
      <footer className="dialog-footer">
        <span className="muted">关闭窗口会取消进行中的检查</span>
        {running ? (
          <button onClick={() => controller.current?.abort()}>取消检查</button>
        ) : (
          <button className="primary" onClick={run}>
            <Play size={15} />
            {result ? '重新检查' : '开始检查'}
          </button>
        )}
      </footer>
    </Modal>
  );
}
