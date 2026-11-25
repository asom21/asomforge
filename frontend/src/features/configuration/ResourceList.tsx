// 按读取、空列表和筛选结果展示配置，保留启用、检查与编辑操作。
import {
  ArrowUpRight,
  CircleAlert,
  LoaderCircle,
  Pencil,
  Plus,
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
  const hasResources = resources.length > 0;
  const EmptyIcon = loading ? LoaderCircle : error ? CircleAlert : Icon;
  return (
    <section
      className={`resource-panel ${!hasResources ? 'is-empty' : ''}`}
      aria-label={`${title} 配置列表`}
      aria-busy={loading}
    >
      {hasResources && (
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
      )}
      {rows.length > 0 && (
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
                        <strong title={resource.name}>{resource.name}</strong>
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
                    {resource.kind === 'models' ? (
                      <div className="model-last-check">
                        {resource.last_check &&
                        resource.last_check.details?.mode !== 'generation' ? (
                          <span className="muted">历史模型列表检查</span>
                        ) : (
                          <Status check={resource.last_check} />
                        )}
                        {resource.last_check?.details?.mode === 'generation' && (
                          <small title={String(resource.last_check.details.model_id ?? '')}>
                            最近测试：
                            {String(
                              resource.last_check.details.model_name ||
                                resource.last_check.details.model_id ||
                                '默认模型',
                            )}
                          </small>
                        )}
                      </div>
                    ) : (
                      <Status check={resource.last_check} />
                    )}
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
                        {resource.kind === 'models' ? '测试' : '检查'}
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
      )}
      {!rows.length && (
        <div className="empty-state" role="status">
          <div className={`empty-symbol ${loading ? 'is-loading' : ''}`} aria-hidden="true">
            <EmptyIcon size={30} className={loading ? 'spin' : ''} />
          </div>
          <h2>
            {loading
              ? '正在读取本机配置…'
              : error
                ? '暂时无法读取配置'
                : hasResources
                  ? '没有匹配的配置'
                  : `让 Agent 连接你的${title === 'MCP' ? '工具与服务' : title === '大模型' ? '模型' : title === '运行平台' ? '运行环境' : '资源'}`}
          </h2>
          <p>
            {loading
              ? '即将就绪，请稍候。'
              : error
                ? '请检查本地服务连接，然后重试。'
                : hasResources
                  ? '试试其他关键词，或切换检查状态。'
                  : `添加第一份 ${title} 配置，从新建开始，或导入已有配置。`}
          </p>
          {!loading && !error && !hasResources && (
            <div className="button-row">
              <button className="primary" onClick={onCreate}>
                <Plus size={17} />
                新建配置
              </button>
              <button onClick={onImport}>
                <Upload size={16} />
                导入配置
                <ArrowUpRight size={14} />
              </button>
            </div>
          )}
        </div>
      )}
      {hasResources && (
        <footer className="list-footer">
          <span>
            显示 {rows.length} / {resources.length} 份配置
          </span>
          <span>保存后可独立检查连接</span>
        </footer>
      )}
    </section>
  );
}
