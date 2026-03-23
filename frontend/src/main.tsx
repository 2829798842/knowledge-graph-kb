/**
 * 模块名称：main
 * 主要功能：挂载 React 前端应用入口。
 */

import React from 'react';
import ReactDOM from 'react-dom/client';

import App from './app';
import './styles/app.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
