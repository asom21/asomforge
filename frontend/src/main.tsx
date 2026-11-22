// 挂载 React 应用并加载全局样式。
import { createRoot } from 'react-dom/client';
import { App } from './app/App';
import './styles/base.css';
import './styles/configuration.css';
import './styles/editor.css';

createRoot(document.getElementById('root')!).render(<App />);
