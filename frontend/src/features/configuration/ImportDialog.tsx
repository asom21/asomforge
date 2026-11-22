// 组织文件选择、导入预览、重名策略和保存结果展示。
import { useRef, useState } from 'react';
import { FileUp, FolderOpen, Upload, X } from 'lucide-react';
import {
  api,
  errorMessage,
  type ImportPreview,
  type ImportResults,
  type Kind,
} from '../../api/client';
import { Modal } from '../../components/Modal';
import { categories } from './catalog';

export function ImportDialog({
  kind,
  onClose,
  onUpdated,
}: {
  kind: Kind;
  onClose: () => void;
  onUpdated: () => void;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const [text, setText] = useState('');
  const [source, setSource] = useState<'files' | 'text'>('files');
  const [policy, setPolicy] = useState('skip');
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [results, setResults] = useState<ImportResults | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const directory = useRef<HTMLInputElement>(null);
  const category = categories.find((item) => item.key === kind)!;
  function body() {
    if (source === 'text') return { text, policy };
    const data = new FormData();
    for (const file of files) data.append('files', file, file.webkitRelativePath || file.name);
    data.append('policy', policy);
    return data;
  }
  function select(selected: FileList | null) {
    setFiles(Array.from(selected || []));
    setPreview(null);
    setError('');
  }
  async function submit() {
    setBusy(true);
    setError('');
    try {
      if (!preview) setPreview(await api.import<ImportPreview>(kind, 'preview', body()));
      else {
        setResults(await api.import<ImportResults>(kind, 'commit', body()));
        onUpdated();
      }
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      className="import-dialog"
      label={`导入 ${category.title}`}
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <header className="dialog-header">
        <div>
          <span className="muted">
            {results ? '导入结果' : preview ? '确认导入内容' : '添加已有配置'}
          </span>
          <h2>导入 {category.title}</h2>
        </div>
        <button className="icon-button" disabled={busy} onClick={onClose} aria-label="关闭导入">
          <X size={20} />
        </button>
      </header>
      <div className="dialog-body">
        {!preview && !results && (
          <>
            {kind !== 'skills' && (
              <div className="segmented" aria-label="导入来源">
                <button
                  className={source === 'files' ? 'selected' : ''}
                  onClick={() => setSource('files')}
                >
                  选择文件
                </button>
                <button
                  className={source === 'text' ? 'selected' : ''}
                  onClick={() => setSource('text')}
                >
                  粘贴 JSON
                </button>
              </div>
            )}
            {source === 'files' ? (
              <>
                <div className="upload-zone">
                  <div className="upload-icon">
                    <FileUp size={28} />
                  </div>
                  <h3>{files.length ? `已选择 ${files.length} 个文件` : '选择要导入的文件'}</h3>
                  <p>{category.hint}</p>
                  <div className="button-row">
                    <button onClick={() => input.current?.click()}>
                      <Upload size={16} />
                      选择文件
                    </button>
                    {kind === 'skills' && (
                      <button onClick={() => directory.current?.click()}>
                        <FolderOpen size={16} />
                        选择目录
                      </button>
                    )}
                  </div>
                </div>
                <input
                  hidden
                  type="file"
                  multiple
                  ref={input}
                  accept={
                    kind === 'skills' ? '.zip,.md' : kind === 'prompts' ? '.json,.md,.txt' : '.json'
                  }
                  onChange={(e) => select(e.target.files)}
                />
                <input
                  hidden
                  type="file"
                  multiple
                  ref={directory}
                  {...{ webkitdirectory: '' }}
                  onChange={(e) => select(e.target.files)}
                />
                {files.length > 0 && (
                  <div className="selected-files">
                    {files.slice(0, 8).map((file, index) => (
                      <div key={index}>
                        {file.webkitRelativePath || file.name}
                        <small>{Math.ceil(file.size / 1024)} KB</small>
                      </div>
                    ))}
                    {files.length > 8 && <small>另有 {files.length - 8} 个文件</small>}
                  </div>
                )}
              </>
            ) : (
              <label className="field">
                <span>{kind === 'mcp' ? 'mcpServers JSON 配置' : '本平台资源 JSON'}</span>
                <textarea
                  className="code-input"
                  rows={14}
                  value={text}
                  onChange={(e) => {
                    setText(e.target.value);
                    setPreview(null);
                  }}
                  spellCheck={false}
                  placeholder={
                    kind === 'mcp'
                      ? '{\n  "mcpServers": {\n    "my-server": { "command": "npx", "args": [] }\n  }\n}'
                      : '{ "name": "配置名称", "config": { … } }'
                  }
                />
              </label>
            )}
            <p className="helper-note">先预览再保存，导入不会启动命令或连接外部服务。</p>
          </>
        )}
        {preview && !results && (
          <>
            <div className="import-preview">
              {preview.items.map((item, index) => (
                <article key={index}>
                  <div>
                    <strong>{item.name}</strong>
                    <span className={`tag ${item.error ? 'danger' : ''}`}>
                      {item.error ? '校验失败' : item.conflict ? '名称重复' : '可导入'}
                    </span>
                  </div>
                  {item.error && <p className="error-text">{item.error}</p>}
                  {item.warnings.map((warning) => (
                    <p className="warning-text" key={warning}>
                      {warning}
                    </p>
                  ))}
                  {!!item.files.length && <small>包含 {item.files.length} 个文件</small>}
                </article>
              ))}
            </div>
            <label className="field">
              <span>遇到同名配置时</span>
              <select value={policy} onChange={(e) => setPolicy(e.target.value)}>
                <option value="skip">保留已有，跳过重复</option>
                <option value="replace">替换已有，保留原 ID</option>
                <option value="copy">另存一份，使用新 ID</option>
              </select>
            </label>
          </>
        )}
        {results && (
          <div className="import-preview">
            {results.results.map((row, index) => (
              <article key={index}>
                <div>
                  <strong>{row.name}</strong>
                  <span className={`tag ${row.status === 'failed' ? 'danger' : ''}`}>
                    {row.status === 'saved'
                      ? '已保存'
                      : row.status === 'skipped'
                        ? '已跳过'
                        : '保存失败'}
                  </span>
                </div>
                {row.error && <p className="error-text">{row.error}</p>}
                {row.warning && <p className="warning-text">{row.warning}</p>}
              </article>
            ))}
          </div>
        )}
        {error && (
          <div className="error-box" role="alert">
            {error}
          </div>
        )}
      </div>
      <footer className="dialog-footer">
        <span className="muted">
          {results
            ? '处理完成，请查看各条结果'
            : preview
              ? `${preview.items.length} 个条目待处理`
              : '凭据会分离到本机私密文件'}
        </span>
        <div>
          {preview && !results && (
            <button disabled={busy} onClick={() => setPreview(null)}>
              返回修改
            </button>
          )}
          {results ? (
            <button className="primary" onClick={onClose}>
              完成
            </button>
          ) : (
            <button
              className="primary"
              disabled={busy || (!preview && (source === 'files' ? !files.length : !text.trim()))}
              onClick={submit}
            >
              {busy ? '处理中…' : preview ? '确认导入' : '解析并预览'}
            </button>
          )}
        </div>
      </footer>
    </Modal>
  );
}
