// 展示配置搜索、启用开关、检查状态和行内操作。
import {
  ArrowUpRight,
  Database,
  Pencil,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
  Upload,
  type LucideIcon,
} from 'lucide-react';
import type { Resource } from '../../api/client';
import { summary } from './catalog';
import { Status } from './CheckPanel';

interface Props {
  title: string;
  Icon: LucideIcon;
  resources: Resource[];
  rows: Resource[];
  query: string;
  setQuery: (value: string) => void;
  filter: string;
  setFilter: (value: string) => void;
  loading: boolean;
  error: string;
  deleting: string | null;
  toggling: string[];
  onEdit: (resource: Resource) => void;
  onCheck: (resource: Resource) => void;
  onDelete: (resource: Resource) => void;
  onToggleEnabled: (resource: Resource) => void;
  onImport: () => void;
  onCreate: () => void;
  onRefresh: () => void;
}

export function ResourceList({
  title,
  Icon,
  resources,
  rows,
  query,
  setQuery,
  filter,
  setFilter,
  loading,
  error,
  deleting,
  toggling,
  onEdit,
  onCheck,
  onDelete,
  onToggleEnabled,
  onImport,
  onCreate,
  onRefresh,
}: Props) {
  return (
    <section className="resource-panel" aria-label={`${title} 配置列表`}>
      <div className="list-toolbar">
        <label className="search-input">
          <Search size={17} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={`搜索 ${title} 配置…`}
            aria-label="搜索配置"
          />
        </label>
        <div className="list-controls">
          <select
            aria-label="筛选检查状态"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="all">全部状态</option>
            <option value="unchecked">尚未检查</option>
            <option value="passed">检查通过</option>
            <option value="limited">部分确认</option>
            <option value="failed">检查未通过</option>
          </select>
          <button className="icon-button" aria-label="刷新列表" onClick={onRefresh}>
            <RefreshCw size={16} className={loading ? 'spin' : ''} />
          </button>
        </div>
      </div>
      <div className="resource-table-wrap">
        <table className="resource-table">
          <thead>
            <tr>
              <th>配置名称</th>
              <th>启用状态</th>
              <th>最近检查</th>
              <th>更新时间</th>
              <th className="operations-heading">操作</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((resource) => (
              <tr key={resource.id}>
                <td>
                  <button className="resource-title" onClick={() => onEdit(resource)}>
                    <span className="resource-icon">
                      <Icon size={18} />
                    </span>
                    <span>
                      <strong>{resource.name}</strong>
                      <small title={summary(resource)}>
                        {resource.description || summary(resource)}
                      </small>
                    </span>
                  </button>
                </td>
                <td>
                  <button
                    className="enable-toggle"
                    role="switch"
                    aria-label={`启用 ${resource.name}`}
                    aria-checked={resource.enabled ?? true}
                    aria-busy={toggling.includes(resource.id)}
                    disabled={toggling.includes(resource.id)}
                    onClick={() => onToggleEnabled(resource)}
                  >
                    <span className="toggle-track" aria-hidden="true">
                      <span />
                    </span>
                    <span>{resource.enabled === false ? '已停用' : '已启用'}</span>
                  </button>
                </td>
                <td>
                  <Status check={resource.last_check} />
                </td>
                <td className="date-cell">
                  {resource.updated_at
                    ? new Date(resource.updated_at).toLocaleDateString('zh-CN')
                    : '—'}
                  <small>r{resource.revision}</small>
                </td>
                <td>
                  <div className="row-actions">
                    <button className="text-button" onClick={() => onCheck(resource)}>
                      <ShieldCheck size={15} />
                      检查
                    </button>
                    <button
                      className="icon-button"
                      aria-label={`编辑 ${resource.name}`}
                      onClick={() => onEdit(resource)}
                    >
                      <Pencil size={15} />
                    </button>
                    <button
                      className="icon-button delete-button"
                      disabled={deleting === resource.id}
                      aria-label={`删除 ${resource.name}`}
                      onClick={() => onDelete(resource)}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!rows.length && (
        <div className="empty-state">
          <div className="empty-symbol">
            <Icon size={31} />
          </div>
          <h2>
            {loading
              ? '正在读取本机配置…'
              : error
                ? '暂时无法读取配置'
                : resources.length
                  ? '没有匹配的配置'
                  : `添加第一份 ${title} 配置`}
          </h2>
          <p>
            {resources.length
              ? '试试其他关键词，或切换检查状态。'
              : '从已有配置开始，也可以按需新建。保存后，随时检查和调整。'}
          </p>
          {!loading && !error && !resources.length && (
            <div className="button-row">
              <button onClick={onImport}>
                <Upload size={16} />
                导入已有配置
              </button>
              <button className="text-button" onClick={onCreate}>
                新建配置
                <ArrowUpRight size={15} />
              </button>
            </div>
          )}
        </div>
      )}
      <footer className="list-footer">
        <span>{rows.length} 份配置</span>
        <span>
          <Database size={13} />
          本地文件存储
        </span>
      </footer>
    </section>
  );
}
