// 挂载 React 应用并加载全局样式。
import { createRoot } from 'react-dom/client';
import { App } from './app/App';
import { initializeTheme } from './app/theme';
import './styles/base.css';
import './styles/configuration.css';
import './styles/editor.css';
import './styles/models.css';

initializeTheme();
createRoot(document.getElementById('root')!).render(<App />);
