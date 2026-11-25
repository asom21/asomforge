// 编辑资源配置与私密字段，处理保存和未保存内容提醒。
import { useEffect, useState, type FormEvent } from 'react';
import { Code2, File, LockKeyhole, Save, X } from 'lucide-react';
import { api, errorMessage, type Kind, type Resource } from '../../api/client';
import { Modal } from '../../components/Modal';
import { ConfigurationFields, Field } from './forms/ConfigurationFields';
import { configFromValues, initialValues, makeDraft } from './forms/values';
import { categories } from './catalog';

export function ResourceEditor({
  kind,
  resource,
  onClose,
  onSaved,
}: {
  kind: Kind;
  resource?: Resource;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [values, setValues] = useState(() => initialValues(kind, resource));
  const [baseline] = useState(() => JSON.stringify(initialValues(kind, resource)));
  const [clear, setClear] = useState<string[]>([]);
  const [jsonMode, setJsonMode] = useState(false);
  const [rawJson, setRawJson] = useState('');
  const [jsonDirty, setJsonDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [files, setFiles] = useState<{ path: string; size: number }[]>([]);
  const dirty = JSON.stringify(values) !== baseline || clear.length > 0 || jsonDirty;
  const title = categories.find((item) => item.key === kind)!.title;
  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (dirty) event.preventDefault();
    };
    window.addEventListener('beforeunload', beforeUnload);
    return () => window.removeEventListener('beforeunload', beforeUnload);
  }, [dirty]);
  useEffect(() => {
    if (resource && kind === 'skills') {
      api
        .files(resource.id)
        .then(setFiles)
        .catch((error) => setError(errorMessage(error)));
    }
  }, [resource, kind]);
  const close = () => {
    if (!busy && (!dirty || window.confirm('放弃未保存的修改？'))) onClose();
  };
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api.save(
        kind,
        makeDraft(kind, values, resource, clear, jsonMode ? rawJson : undefined),
        resource?.id,
      );
      onSaved();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  const toggleJson = () => {
    try {
      if (jsonMode) {
        const config = JSON.parse(rawJson);
        setValues(
          initialValues('mcp', {
            name: values.name,
            description: values.description,
            config,
          }),
        );
      } else {
        setRawJson(JSON.stringify(configFromValues(kind, values), null, 2));
      }
      setJsonMode(!jsonMode);
      setError('');
    } catch {
      setError('JSON 格式不正确，请先修正后切换');
    }
  };
  return (
    <Modal
      className="editor-dialog"
      label={`${resource ? '编辑' : '新建'} ${title}`}
      onClose={close}
    >
      <header className="dialog-header">
        <div>
          <span className="muted">配置中心 / {title}</span>
          <h2>{resource ? '编辑配置' : '新建配置'}</h2>
        </div>
        <button className="icon-button" aria-label="关闭编辑" onClick={close} disabled={busy}>
          <X size={20} />
        </button>
      </header>
      <form onSubmit={save}>
        <div className="dialog-body">
          <Field label="显示名称">
            <input
              required
              maxLength={160}
              value={values.name}
              onChange={(e) => setValues({ ...values, name: e.target.value })}
              placeholder={`为这份 ${title} 配置命名`}
              autoFocus
            />
          </Field>
          <Field label="说明（可选）">
            <input
              value={values.description}
              onChange={(e) => setValues({ ...values, description: e.target.value })}
              placeholder="记录用途，方便之后选用"
            />
          </Field>
          <div className="section-label">
            <h3>配置内容</h3>
            {kind === 'mcp' && (
              <button type="button" className="text-button" onClick={toggleJson}>
                <Code2 size={15} />
                {jsonMode ? '表单编辑' : 'JSON 编辑'}
              </button>
            )}
          </div>
          {jsonMode ? (
            <Field label="MCP 服务定义" hint="此处填写单个服务对象；批量 mcpServers 请使用导入。">
              <textarea
                className="code-input"
                rows={17}
                value={rawJson}
                spellCheck={false}
                onChange={(e) => {
                  setRawJson(e.target.value);
                  setJsonDirty(true);
                }}
              />
            </Field>
          ) : (
            <ConfigurationFields
              kind={kind}
              values={values}
              set={(key, value) => setValues({ ...values, [key]: value })}
              secretFields={resource?.secret_fields || []}
            />
          )}
          {!!resource?.secret_fields.length && (
            <details className="secret-options">
              <summary>
                <LockKeyhole size={14} /> 已保存的私密字段
              </summary>
              <p>勾选后将在本次保存时清除。删除环境变量或请求头的键，也会移除对应值。</p>
              {resource.secret_fields.map((name) => (
                <label className="checkbox-row" key={name}>
                  <input
                    type="checkbox"
                    checked={clear.includes(name)}
                    onChange={(e) =>
                      setClear(
                        e.target.checked
                          ? [...clear, name]
                          : clear.filter((field) => field !== name),
                      )
                    }
                  />
                  清除 {name}
                </label>
              ))}
            </details>
          )}
          {!!files.length && (
            <section className="file-list">
              <h3>包内文件</h3>
              {files.map((file) => (
                <div key={file.path}>
                  <File size={14} />
                  <code>{file.path}</code>
                  <small>{file.size} B</small>
                </div>
              ))}
            </section>
          )}
          {error && (
            <div className="error-box" role="alert">
              {error}
            </div>
          )}
        </div>
        <footer className="dialog-footer">
          <span className="muted">{dirty ? '有未保存的修改' : '配置保存在本机'}</span>
          <div>
            <button type="button" onClick={close} disabled={busy}>
              取消
            </button>
            <button className="primary" type="submit" disabled={busy}>
              <Save size={16} />
              {busy ? '保存中…' : '保存配置'}
            </button>
          </div>
        </footer>
      </form>
    </Modal>
  );
}
