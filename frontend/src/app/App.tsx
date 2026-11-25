// 组合配置中心页面，管理分类、列表状态和资源操作。
import { useEffect, useState } from 'react';
import { ChevronRight, Plus, ShieldCheck, SlidersHorizontal, Upload } from 'lucide-react';
import {
  api,
  errorMessage,
  type Catalog,
  type Category,
  type Kind,
  type Resource,
} from '../api/client';
import { categories, summary } from '../features/configuration/catalog';
import { ResourceEditor } from '../features/configuration/ResourceEditor';
import { CheckPanel } from '../features/configuration/CheckPanel';
import { ImportDialog } from '../features/configuration/ImportDialog';
import { ResourceList } from '../features/configuration/ResourceList';
import { ModelConnectionEditor } from '../features/configuration/models/ModelConnectionEditor';
import { ModelCheckDialog } from '../features/configuration/models/ModelCheckDialog';
import { Sidebar } from './Sidebar';
import { ThemeToggle } from './ThemeToggle';

export function App() {
  const [category, setCategory] = useState<Category>('mcp');
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [resources, setResources] = useState<Resource[]>([]);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [revision, refresh] = useState(0);
  const [editor, setEditor] = useState<Resource | 'new' | null>(null);
  const [checking, setChecking] = useState<Resource | null>(null);
  const [importing, setImporting] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [toggling, setToggling] = useState<string[]>([]);
  const current = categories.find((item) => item.key === category)!;
  const Icon = current.icon;
  const isTool = category === 'tools';
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    setLoading(true);
    setResources([]);
    Promise.all([
      api.catalog(),
      category === 'tools' ? Promise.resolve([]) : api.list(category, controller.signal),
    ])
      .then(([catalog, rows]) => {
        if (!controller.signal.aborted) {
          setCatalog(catalog);
          setResources(rows);
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) setError(errorMessage(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [category, revision]);
  useEffect(() => {
    if (notice) {
      const timer = window.setTimeout(() => setNotice(''), 4000);
      return () => clearTimeout(timer);
    }
  }, [notice]);
  const update = () => refresh((value) => value + 1);
  const rows = resources.filter(
    (resource) =>
      [resource.name, resource.description, summary(resource)]
        .join(' ')
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (filter === 'all' ||
        (filter === 'unchecked' ? !resource.last_check : resource.last_check?.status === filter)),
  );
  async function remove(resource: Resource) {
    if (!window.confirm(`删除“${resource.name}”？本机保存的配置与对应私密值会一并移除。`)) return;
    setDeleting(resource.id);
    try {
      await api.delete(resource);
      setNotice('配置已删除');
      update();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setDeleting(null);
    }
  }
  async function toggleEnabled(resource: Resource) {
    setToggling((ids) => [...ids, resource.id]);
    setError('');
    try {
      const updated = await api.setEnabled(resource, !(resource.enabled ?? true));
      setResources((rows) => rows.map((row) => (row.id === updated.id ? updated : row)));
      setNotice(`${updated.enabled ? '已启用' : '已停用'} ${updated.name}`);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setToggling((ids) => ids.filter((id) => id !== resource.id));
    }
  }
  return (
    <div className="app-shell">
      <Sidebar
        category={category}
        catalog={catalog}
        onSelect={(key) => {
          setCategory(key);
          setQuery('');
          setFilter('all');
        }}
      />
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumbs">
            <SlidersHorizontal size={16} />
            <span>配置中心</span>
            <ChevronRight size={14} />
            <strong>{current.title}</strong>
          </div>
          <ThemeToggle />
        </header>
        <main>
          <div className="page-heading">
            <div>
              <div className="title-line">
                <span className="category-symbol">
                  <Icon size={24} />
                </span>
                <h1>{current.title}</h1>
                <span className="count-badge">{isTool ? '暂未开放' : resources.length}</span>
              </div>
              <p>{current.subtitle}</p>
            </div>
            {!isTool && (resources.length > 0 || !!error) && (
              <div className="button-row">
                <button onClick={() => setImporting(true)}>
                  <Upload size={16} />
                  导入配置
                </button>
                <button className="primary" onClick={() => setEditor('new')}>
                  <Plus size={17} />
                  新建配置
                </button>
              </div>
            )}
          </div>
          {error && (
            <div className="error-box page-error" role="alert">
              {error}
              <button className="text-button" onClick={update}>
                重试
              </button>
            </div>
          )}
          {isTool ? (
            <section className="tool-placeholder">
              <div className="empty-symbol">
                <Icon size={34} />
              </div>
              <h2>Tool 即将开放</h2>
              <p>这里将管理可供 Agent 使用的本地工具。</p>
              <small>目前可先配置 Skill、MCP、Prompt、大模型和运行平台。</small>
            </section>
          ) : (
            <>
              <ResourceList
                title={current.title}
                Icon={Icon}
                resources={resources}
                rows={rows}
                query={query}
                setQuery={setQuery}
                filter={filter}
                setFilter={setFilter}
                loading={loading}
                error={error}
                deleting={deleting}
                toggling={toggling}
                onToggleEnabled={toggleEnabled}
                onEdit={setEditor}
                onCheck={setChecking}
                onDelete={remove}
                onImport={() => setImporting(true)}
                onCreate={() => setEditor('new')}
                onRefresh={update}
              />
            </>
          )}
        </main>
      </div>
      {notice && (
        <div className="toast" role="status">
          <ShieldCheck size={16} />
          {notice}
        </div>
      )}
      {editor && category === 'models' && (
        <ModelConnectionEditor
          resource={editor === 'new' ? undefined : editor}
          onClose={() => setEditor(null)}
          onSaved={() => {
            setEditor(null);
            setNotice('模型连接已保存');
            update();
          }}
        />
      )}
      {editor && !isTool && category !== 'models' && (
        <ResourceEditor
          kind={category as Kind}
          resource={editor === 'new' ? undefined : editor}
          onClose={() => setEditor(null)}
          onSaved={() => {
            setEditor(null);
            setNotice('配置已保存');
            update();
          }}
        />
      )}
      {checking &&
        (checking.kind === 'models' ? (
          <ModelCheckDialog
            resource={checking}
            onClose={() => setChecking(null)}
            onUpdated={update}
          />
        ) : (
          <CheckPanel resource={checking} onClose={() => setChecking(null)} onUpdated={update} />
        ))}
      {importing && !isTool && (
        <ImportDialog
          kind={category as Kind}
          onClose={() => setImporting(false)}
          onUpdated={update}
        />
      )}
    </div>
  );
}
