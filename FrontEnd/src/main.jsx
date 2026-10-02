import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './index.css';   // Tailwind + tokens do tema
import './legacy.css'; // estilos antigos, em migração (ver cabeçalho do arquivo)

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
