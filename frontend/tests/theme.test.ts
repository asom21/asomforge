// 验证主题偏好优先级、系统变化以及存储受限时的切换行为。
import assert from 'node:assert/strict';
import { test } from 'node:test';

async function environment(options: { dark?: boolean; saved?: string; blocked?: boolean } = {}) {
  const storage = new Map<string, string>();
  if (options.saved) storage.set('asomforge.theme', options.saved);
  const media = new EventTarget() as EventTarget & { matches: boolean };
  media.matches = options.dark ?? false;
  const root = { dataset: {} as Record<string, string> };
  Object.defineProperty(globalThis, 'document', {
    configurable: true,
    value: { documentElement: root },
  });
  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: {
      matchMedia: () => media,
      get localStorage() {
        if (options.blocked) throw new Error('Storage blocked');
        return {
          getItem: (key: string) => storage.get(key) ?? null,
          setItem: (key: string, value: string) => storage.set(key, value),
        };
      },
    },
  });
  const theme = await import(`../src/app/theme.ts?test=${crypto.randomUUID()}`);
  theme.initializeTheme();
  return { theme, root, storage, media };
}

test('首次采用系统深色偏好，且不将自动选择写入存储', async () => {
  const { theme, root, storage } = await environment({ dark: true });
  assert.equal(theme.getTheme(), 'dark');
  assert.equal(root.dataset.theme, 'dark');
  assert.equal(storage.has('asomforge.theme'), false);
});

test('已保存的手动选择优先于系统偏好', async () => {
  const { theme, root } = await environment({ dark: true, saved: 'light' });
  assert.equal(theme.getTheme(), 'light');
  assert.equal(root.dataset.theme, 'light');
});

test('切换主题通知订阅者并保存，取消订阅后不再通知', async () => {
  const { theme, root, storage } = await environment();
  let notifications = 0;
  const unsubscribe = theme.subscribeTheme(() => notifications++);
  theme.toggleTheme();
  assert.equal(root.dataset.theme, 'dark');
  assert.equal(storage.get('asomforge.theme'), 'dark');
  assert.equal(notifications, 1);
  unsubscribe();
  theme.toggleTheme();
  assert.equal(theme.getTheme(), 'light');
  assert.equal(notifications, 1);
});

test('存储被禁用时仍可跟随系统并手动切换', async () => {
  const { theme, root, media } = await environment({ blocked: true, dark: true });
  assert.equal(root.dataset.theme, 'dark');
  theme.toggleTheme();
  assert.equal(root.dataset.theme, 'light');
  media.dispatchEvent(new Event('change'));
  assert.equal(root.dataset.theme, 'light');
});

test('仅在没有手动选择时响应系统主题变化', async () => {
  const { theme, media, root } = await environment();
  media.matches = true;
  media.dispatchEvent(new Event('change'));
  assert.equal(root.dataset.theme, 'dark');
  theme.toggleTheme();
  media.dispatchEvent(new Event('change'));
  assert.equal(root.dataset.theme, 'light');
});

test('无效的存储值回退系统主题', async () => {
  const { root } = await environment({ saved: 'invalid', dark: true });
  assert.equal(root.dataset.theme, 'dark');
});
