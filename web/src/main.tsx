/**
 * 应用入口文件
 */

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';

// 导入全局样式
import '@/styles/global.css';

// 获取根元素
const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('找不到根元素 #root');
}

// 创建 React 根
const root = createRoot(rootElement);

// 渲染应用
root.render(
  <StrictMode>
    <App />
  </StrictMode>
);
