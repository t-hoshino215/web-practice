import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './App';
import './styles/global.css';

const container = document.getElementById('root');

// index.html に #root が無い状態は設定ミス。黙って無視せず即座に失敗させる
if (container === null) {
  throw new Error('Root element (#root) not found in index.html');
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
