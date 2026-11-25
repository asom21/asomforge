// 提供主题切换按钮，并从按钮中心以圆形展开新主题。
import { useRef, useSyncExternalStore } from 'react';
import { flushSync } from 'react-dom';
import { Moon, Sun } from 'lucide-react';
import { getTheme, subscribeTheme, toggleTheme } from './theme';

export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribeTheme, getTheme);
  const revealing = useRef(false);
  const label = theme === 'dark' ? '切换为浅色模式' : '切换为深色模式';

  async function switchTheme(button: HTMLButtonElement) {
    if (revealing.current) return;
    if (
      !document.startViewTransition ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      toggleTheme();
      return;
    }

    const bounds = button.getBoundingClientRect();
    const x = bounds.left + bounds.width / 2;
    const y = bounds.top + bounds.height / 2;
    const radius = Math.ceil(
      Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y)),
    );
    const root = document.documentElement;
    revealing.current = true;
    root.classList.add('theme-reveal');
    let transition: ViewTransition | undefined;
    try {
      transition = document.startViewTransition(() => flushSync(toggleTheme));
      await transition.ready;
      const animation = root.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
        {
          duration: 550,
          easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
          pseudoElement: '::view-transition-new(root)',
          fill: 'both',
        },
      );
      try {
        await animation.finished;
      } finally {
        animation.cancel();
      }
    } catch {
      // 页面不可见或浏览器跳过动画时，保留已切换的主题并清理过渡。
      if (transition) transition.skipTransition();
      else toggleTheme();
    } finally {
      if (transition) await transition.finished.catch(() => {});
      root.classList.remove('theme-reveal');
      revealing.current = false;
    }
  }

  return (
    <button
      className="theme-toggle"
      aria-label={label}
      title={label}
      onClick={(event) => void switchTheme(event.currentTarget)}
    >
      {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
      <span>{theme === 'dark' ? '浅色模式' : '深色模式'}</span>
    </button>
  );
}
