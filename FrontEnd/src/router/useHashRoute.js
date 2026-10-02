import { useState, useEffect } from 'react';

export const NAV = [
  { id: 'dashboard', label: 'Painel', icon: 'grid' },
  { id: 'alunos', label: 'Alunos', icon: 'users' },
  { id: 'funcionarios', label: 'Funcionários', icon: 'briefcase' },
  { id: 'cadastro', label: 'Cadastro facial', icon: 'userplus' },
  { id: 'monitoramento', label: 'Monitoramento', icon: 'activity' },
  { id: 'alertas', label: 'Alertas', icon: 'bell' },
  { id: 'relatorios', label: 'Relatórios', icon: 'chart' },
  { id: 'configuracoes', label: 'Configurações', icon: 'gear' },
];

function parseHash() {
  const h = window.location.hash.replace(/^#\/?/, '');
  const parts = h.split('/').filter(Boolean);
  return { view: parts[0] || 'dashboard', params: parts.slice(1) };
}

export function useHashRoute() {
  const [route, setRoute] = useState(parseHash());

  useEffect(() => {
    const onChange = () => setRoute(parseHash());
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);

  function navigate(view, ...params) {
    window.location.hash = '/' + [view, ...params].join('/');
    setRoute({ view, params });
  }

  return [route, navigate];
}
