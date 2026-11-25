// 选择已保存连接中的单个模型并显示与配置版本关联的测试结果。
import { useState } from 'react';
import { X } from 'lucide-react';
import type { Resource } from '../../../api/client';
import { Modal } from '../../../components/Modal';
import { ModelProbe } from './ModelProbe';
import { connectionConfig, initialConnection } from './values';

export function ModelCheckDialog({
  resource,
  onClose,
  onUpdated,
}: {
  resource: Resource;
  onClose: () => void;
  onUpdated: () => void;
}) {
  const [config] = useState(() => {
    try {
      return connectionConfig(initialConnection(resource));
    } catch {
      return null;
    }
  });
  const [selected, setSelected] = useState(config?.default_model_id ?? '');
  const [busy, setBusy] = useState(false);
  const model = config?.models.find((m) => m.id === selected);
  const checks = resource.model_checks;
  const stored = checks?.[selected];
  return (
    <Modal className="check-dialog model-check-dialog" label="模型连通性测试" onClose={onClose}>
      <header className="dialog-header">
        <div>
          <span className="muted">已保存连接 · r{resource.revision}</span>
          <h2>{resource.name}</h2>
        </div>
        <button className="icon-button" onClick={onClose} aria-label="关闭检查">
          <X size={20} />
        </button>
      </header>
      <div className="dialog-body">
        {model && config ? (
          <>
            <label className="field">
              <span>选择测试模型</span>
              <select
                aria-label="选择测试模型"
                value={selected}
                disabled={busy}
                onChange={(e) => setSelected(e.target.value)}
              >
                {config.models.map((m) => (
                  <option value={m.id} key={m.id}>
                    {m.name ? `${m.name} · ${m.id}` : m.id}
                    {m.id === config.default_model_id ? '（默认）' : ''}
                  </option>
                ))}
              </select>
            </label>
            <ModelProbe
              key={selected}
              model={model}
              signature={`${resource.id}:${resource.revision}:${selected}`}
              getSource={() => ({ resource_id: resource.id, revision: resource.revision })}
              savedResult={stored?.revision === resource.revision ? stored : null}
              onCompleted={onUpdated}
              onBusyChange={setBusy}
            />
          </>
        ) : (
          <div className="model-warning">当前目录待补全，请先编辑连接并添加有效模型。</div>
        )}
      </div>
      <footer className="dialog-footer">
        <span className="muted">关闭会取消本地请求，远端可能已经产生费用。</span>
        <button onClick={onClose}>关闭</button>
      </footer>
    </Modal>
  );
}
