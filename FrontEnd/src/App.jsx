import { useState, useEffect, useRef } from 'react';
import Icon from './icons/Icon.jsx';
import Sidebar from './components/Sidebar.jsx';
import Topbar from './components/Topbar.jsx';
import Toast from './components/Toast.jsx';
import { useHashRoute, NAV } from './router/useHashRoute.js';
import { seedPeople, seedLogsAndAlerts, janelaDoTurno, limiteDoTurno, baseRng, pick } from './data/seed.js';

import Login from './pages/login/Login.jsx';
import Dashboard from './pages/dashboard/Dashboard.jsx';
import AlunosPage from './pages/alunos/AlunosPage.jsx';
import FuncionariosPage from './pages/funcionarios/FuncionariosPage.jsx';
import CadastroFacial from './pages/cadastro/CadastroFacial.jsx';
import PerfilPessoa from './pages/perfil/PerfilPessoa.jsx';
import Monitoramento from './pages/monitoramento/Monitoramento.jsx';
import Alertas from './pages/alertas/Alertas.jsx';
import Relatorios from './pages/relatorios/Relatorios.jsx';
import Configuracoes from './pages/configuracoes/Configuracoes.jsx';

export default function App() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [route, navigateRaw] = useHashRoute();

  const seedRef = useRef(null);
  if (!seedRef.current) {
    const people = seedPeople();
    const { logs, alerts, nextLogId, nextAlertId } = seedLogsAndAlerts(people);
    seedRef.current = { nextLogId, nextAlertId, nextPersonId: people.length + 1 };
    seedRef.current.initialPeople = people;
    seedRef.current.initialLogs = logs;
    seedRef.current.initialAlerts = alerts;
  }
  const [people, setPeople] = useState(seedRef.current.initialPeople);
  const [logs, setLogs] = useState(seedRef.current.initialLogs);
  const [alerts, setAlerts] = useState(seedRef.current.initialAlerts);
  const [settings, setSettings] = useState({
    notifAtraso: true, notifAusencia: true, notifNaoReconhecido: false, limiteManha: '07:20', limiteTarde: '13:20'
  });
  const [toast, setToast] = useState(null);

  function showToast(msg, icon) { setToast({ msg, icon, key: Date.now() }); }
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2600);
    return () => clearTimeout(t);
  }, [toast]);

  function navigate(view, ...params) { setSidebarOpen(false); navigateRaw(view, ...params); }

  // feed "ao vivo" no Painel e no Monitoramento
  useEffect(() => {
    if (route.view !== 'dashboard' && route.view !== 'monitoramento') return;
    const id = setInterval(() => {
      setPeople(currentPeople => {
        const ativos = currentPeople.filter(p => p.status === 'ativo');
        if (!ativos.length) return currentPeople;
        const p = pick(ativos);
        const [ini, fim] = janelaDoTurno(p.turno);
        const horaMin = ini + Math.floor(baseRng() * (fim - ini));
        const atrasado = horaMin > limiteDoTurno(p.turno);
        setLogs(curLogs => {
          const novoId = seedRef.current.nextLogId++;
          return [...curLogs, {
            id: novoId, personId: p.id, tipo: 'entrada', horaMin,
            status: atrasado ? 'atraso' : 'reconhecido', local: 'Portaria principal'
          }];
        });
        return currentPeople;
      });
    }, 9000);
    return () => clearInterval(id);
  }, [route.view]);

  function addPerson(novo) {
    const id = seedRef.current.nextPersonId++;
    setPeople(cur => [...cur, { id, ...novo }]);
    return id;
  }
  function setPersonStatus(id, status) {
    setPeople(cur => cur.map(p => p.id === id ? { ...p, status } : p));
  }
  function resolverAlerta(id) {
    setAlerts(cur => cur.map(a => a.id === id ? { ...a, status: 'resolvido' } : a));
    showToast('Alerta marcado como resolvido', 'check');
  }

  if (!loggedIn) {
    return <Login onLogin={() => { setLoggedIn(true); navigate('dashboard'); showToast('Bem-vinda, Marina!', 'check'); }} />;
  }

  const pageTitle = (NAV.find(n => n.id === route.view) || { label: 'Perfil' }).label;
  let content;
  switch (route.view) {
    case 'dashboard': content = <Dashboard people={people} logs={logs} alerts={alerts} onNavigate={navigate} />; break;
    case 'alunos': content = <AlunosPage people={people} onNavigate={navigate} />; break;
    case 'funcionarios': content = <FuncionariosPage people={people} onNavigate={navigate} />; break;
    case 'cadastro': content = <CadastroFacial tipoInicial={route.params[0]} onSubmitPerson={addPerson} onNavigate={navigate} showToast={showToast} />; break;
    case 'pessoa': content = <PerfilPessoa tipo={route.params[0]} id={parseInt(route.params[1], 10)} people={people} alerts={alerts} onNavigate={navigate} onSetStatus={setPersonStatus} showToast={showToast} />; break;
    case 'monitoramento': content = <Monitoramento people={people} logs={logs} onNavigate={navigate} />; break;
    case 'alertas': content = <Alertas people={people} alerts={alerts} onResolver={resolverAlerta} />; break;
    case 'relatorios': content = <Relatorios people={people} logs={logs} />; break;
    case 'configuracoes': content = <Configuracoes settings={settings} onChange={setSettings} showToast={showToast} />; break;
    default: content = <Dashboard people={people} logs={logs} alerts={alerts} onNavigate={navigate} />;
  }

  return (
    <>
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-45 bg-[rgba(15,18,25,.45)] nav:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <div className="flex min-h-screen">
        <Sidebar view={route.view} open={sidebarOpen} onNavigate={navigate} onLogout={() => setLoggedIn(false)} />
        <div className="flex min-h-screen min-w-0 flex-1 flex-col nav:ml-60">
          <Topbar title={pageTitle} onToggle={() => setSidebarOpen(o => !o)} />
          <div className="mx-auto w-full max-w-[1180px] flex-1 px-4 pt-5 pb-[50px] nav:px-[34px] nav:pt-[30px] nav:pb-[60px]">
            {content}
          </div>
        </div>
      </div>
      <Toast toast={toast} />
    </>
  );
}
