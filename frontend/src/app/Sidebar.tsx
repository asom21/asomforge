// 展示资源分类导航、本机连接状态与工作空间信息。
import { HardDrive, SlidersHorizontal } from 'lucide-react';
import type { Catalog, Category } from '../api/client';
import { categories } from '../features/configuration/catalog';

export function Sidebar({
  category,
  catalog,
  onSelect,
}: {
  category: Category;
  catalog: Catalog | null;
  onSelect: (category: Category) => void;
}) {
  return (
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="AsomForge 首页">
        <img src="/favicon.svg" alt="" />
        <span>
          AsomForge<small>Agent 工作空间</small>
        </span>
      </a>
      <div className="workspace-name">
        <span className="workspace-avatar">A</span>
        <div>
          <strong>个人工作空间</strong>
          <small>本地运行</small>
        </div>
        <HardDrive size={15} />
      </div>
      <div className="nav-section-label">
        <SlidersHorizontal size={14} />
        配置中心
      </div>
      <nav aria-label="配置分类">
        {categories.map((item) => (
          <button
            key={item.key}
            aria-label={item.title}
            title={item.title}
            className={category === item.key ? 'active' : ''}
            aria-current={category === item.key ? 'page' : undefined}
            onClick={() => {
              onSelect(item.key);
            }}
          >
            <item.icon size={18} />
            <span>{item.title}</span>
            {item.key === 'tools' ? (
              <small className="soon-label">稍后</small>
            ) : (
              <small>{catalog?.counts[item.key] ?? '—'}</small>
            )}
          </button>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <div>
          <span className={`connection-dot ${catalog ? '' : 'offline'}`} />
          {catalog ? '本地服务已连接' : '等待本地服务'}
        </div>
        <small>配置留在本机，按需连接外部服务。</small>
        <span className="version-label">
          AsomForge <span>v0.1.0</span>
        </span>
      </div>
    </aside>
  );
}
