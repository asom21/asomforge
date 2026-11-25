// 管理系统主题与用户选择，向界面同步并仅持久化主题偏好。
type Theme = 'light' | 'dark';
const storageKey = 'asomforge.theme';
const listeners = new Set<() => void>();
let current: Theme = 'light';
let manual = false;

function applyTheme(theme: Theme) {
  current = theme;
  document.documentElement.dataset.theme = theme;
  listeners.forEach((listener) => listener());
}

export function initializeTheme(): void {
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  let saved: string | null = null;
  try {
    saved = window.localStorage.getItem(storageKey);
  } catch {
    // 浏览器禁止存储时，仍使用系统偏好并允许本次会话切换。
  }
  manual = saved === 'dark' || saved === 'light';
  applyTheme(manual ? (saved as Theme) : system.matches ? 'dark' : 'light');
  system.addEventListener('change', () => {
    if (!manual) applyTheme(system.matches ? 'dark' : 'light');
  });
}

export function getTheme(): Theme {
  return current;
}

export function toggleTheme(): void {
  manual = true;
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  try {
    window.localStorage.setItem(storageKey, next);
  } catch {
    // 存储失败不阻断界面交互，当前选择在本次会话内生效。
  }
}

export function subscribeTheme(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
