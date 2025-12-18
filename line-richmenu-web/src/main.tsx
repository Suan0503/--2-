import React from 'react';
import ReactDOM from 'react-dom/client';
import { RichMenuUploader } from './richmenu/RichMenuUploader';

import './styles.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <RichMenuUploader />
  </React.StrictMode>
);
