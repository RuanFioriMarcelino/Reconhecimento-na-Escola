import { useState, useEffect, useCallback, useRef } from 'react';
import Sidebar from './components/Sidebar.jsx';
import Topbar from './components/Topbar.jsx';
import Toast from './components/Toast.jsx';
import { useHashRoute, NAV } from './router/useHashRoute.js';

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
import { api, clearToken, getToken, setUnauthorizedHandler } from './lib/api.js';

export default function App() {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(() => Boolean(getToken()));
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [route, navigateRaw] = useHashRoute();

  const [turmas, setTurmas] = useState([]);
  const [turnos, setTurnos] = useState([]);
  const [dispositivos, setDispositivos] = useState([]);
  const [openAlertsCount, setOpenAlertsCount] = useState(0);
  const [liveTick, setLiveTick] = useState(0);
  const [settings, setSettings] = useState({
    nomeEscola: 'Escola Natálio Vassoler',
    notifAtraso: true,
    notifAusencia: true,
    notifNaoReconhecido: true,
    notifSaidaAntecipada: true,
    limiteManha: '07:20',
    limiteTarde: '13:20',
    saidaManha: '11:30',
    saidaTarde: '17:30',
    cooldownSegundos: 45,
    tempoMinimoPermanenciaMin: 2,
    limiarConfianca: 0.38,
    retencaoLogsDias: 365,
    modoPassivo: true,
  });
  const [toast, setToast] = useState(null);
  const [apiError, setApiError] = useState('');

  const cursorRef = useRef({ lastLogId: 0, lastAlertId: 0 });

  function showToast(msg, icon) {
    setToast({ msg, icon, key: Date.now() });
  }

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3200);
    return () => clearTimeout(t);
  }, [toast]);

  const loadMetadata = useCallback(async (silencioso = true) => {
    try {
      const data = await api.bootstrap();
      setTurmas(data.turmas || []);
      setTurnos(data.turnos || []);
      setDispositivos(data.dispositivos || []);
      setOpenAlertsCount(data.openAlertsCount ?? 0);
      if (data.settings) setSettings(data.settings);
      if (data.cursor) {
        cursorRef.current = {
          lastLogId: data.cursor.lastLogId || 0,
          lastAlertId: data.cursor.lastAlertId || 0,
        };
      }
      setApiError('');
      return true;
    } catch (error) {
      setApiError(error.message || 'Falha ao carregar metadados do servidor.');
      if (!silencioso) showToast(error.message || 'Falha de comunicação com o servidor.', 'triangle');
      return false;
    }
  }, []);

  const runLiveSync = useCallback(async () => {
    if (document.visibilityState !== 'visible') return;
    try {
      const data = await api.live(cursorRef.current.lastLogId, cursorRef.current.lastAlertId);
      setDispositivos(data.dispositivos || []);
      setOpenAlertsCount(data.openAlertsCount ?? 0);
      setApiError('');

      if (data.changed) {
        cursorRef.current = {
          lastLogId: data.lastLogId || cursorRef.current.lastLogId,
          lastAlertId: data.lastAlertId || cursorRef.current.lastAlertId,
        };
        setLiveTick(t => t + 1);

        const highAlert = (data.newAlerts || []).find(a => a.severidade === 'alta' && a.status !== 'resolvido');
        if (highAlert) {
          showToast(`Aviso da portaria: ${highAlert.tipo}`, 'triangle');
        }
      }
    } catch (error) {
      setApiError(error.message || 'Falha de sincronização em tempo real.');
    }
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      setTurmas([]);
      setTurnos([]);
      setDispositivos([]);
      setOpenAlertsCount(0);
    });

    if (!getToken()) {
      setBooting(false);
      return;
    }

    (async () => {
      try {
        const meRes = await api.me();
        setUser(meRes.user);
        await loadMetadata(true);
      } catch {
        clearToken();
        setUser(null);
      } finally {
        setBooting(false);
      }
    })();
  }, [loadMetadata]);

  // Sincronização incremental leve (/api/live/) com pausa automática em abas ocultas
  useEffect(() => {
    if (!user) return;
    const interval = setInterval(() => {
      runLiveSync();
    }, 3000);

    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        runLiveSync();
      }
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [user, runLiveSync]);

  function navigate(view, ...params) {
    setSidebarOpen(false);
    navigateRaw(view, ...params);
  }

  async function addPerson(novo, faceFiles, existingPersonId = null) {
    let targetId = existingPersonId;
    if (!targetId) {
      const created = await api.createPerson(novo);
      targetId = created.id;
    }
    if (faceFiles && faceFiles.length > 0) {
      try {
        await api.enrollBiometrics(targetId, faceFiles);
      } catch (err) {
        err.savedPersonId = targetId;
        throw err;
      }
    }
    setLiveTick(t => t + 1);
    return targetId;
  }

  async function addClass(data) {
    const created = await api.classesCreate(data);
    if (data.tipo === 'turno') setTurnos(cur => [...cur, created]);
    else setTurmas(cur => [...cur, created]);
  }

  async function saveSettings(nextSettings) {
    const res = await api.updateSettings(nextSettings);
    setSettings(res.settings);
    showToast('Configurações salvas no PostgreSQL', 'check');
  }

  async function handleLogout() {
    await api.logout();
    setUser(null);
    setTurmas([]);
    setTurnos([]);
    setDispositivos([]);
    setOpenAlertsCount(0);
  }

  if (booting) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg text-ink-soft">
        Validando sessão segura...
      </div>
    );
  }

  if (!user) {
    return (
      <>
        <Login
          onLogin={async (email, senha) => {
            const res = await api.login(email, senha);
            setUser(res.user);
            await loadMetadata(true);
            navigate('dashboard');
            showToast(`Bem-vindo(a), ${res.user.nome}!`, 'check');
          }}
        />
        <Toast toast={toast} />
      </>
    );
  }

  const pageTitle = (NAV.find(n => n.id === route.view) || { label: 'Perfil' }).label;
  let content;
  switch (route.view) {
    case 'dashboard':
      content = <Dashboard user={user} liveTick={liveTick} onNavigate={navigate} />;
      break;
    case 'alunos':
      content = <AlunosPage turmas={turmas} liveTick={liveTick} onNavigate={navigate} />;
      break;
    case 'funcionarios':
      content = <FuncionariosPage liveTick={liveTick} onNavigate={navigate} />;
      break;
    case 'cadastro':
      content = <CadastroFacial tipoInicial={route.params[0]} turmas={turmas} onSubmitPerson={addPerson} onNavigate={navigate} showToast={showToast} />;
      break;
    case 'pessoa':
      content = (
        <PerfilPessoa
          tipo={route.params[0]}
          id={route.params[1]}
          liveTick={liveTick}
          onNavigate={navigate}
          showToast={showToast}
        />
      );
      break;
    case 'monitoramento':
      content = <Monitoramento dispositivos={dispositivos} liveTick={liveTick} onNavigate={navigate} />;
      break;
    case 'alertas':
      content = <Alertas liveTick={liveTick} onAlertChanged={() => runLiveSync()} showToast={showToast} />;
      break;
    case 'relatorios':
      content = <Relatorios liveTick={liveTick} showToast={showToast} />;
      break;
    case 'configuracoes':
      content = (
        <Configuracoes
          user={user}
          settings={settings}
          onSaveSettings={saveSettings}
          turmas={turmas}
          turnos={turnos}
          dispositivos={dispositivos}
          onAddClass={addClass}
          onRefresh={() => loadMetadata(true)}
          showToast={showToast}
        />
      );
      break;
    default:
      content = <Dashboard user={user} liveTick={liveTick} onNavigate={navigate} />;
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
        <Sidebar
          user={user}
          view={route.view}
          open={sidebarOpen}
          openAlertsCount={openAlertsCount}
          onNavigate={navigate}
          onLogout={handleLogout}
        />
        <div className="flex min-h-screen min-w-0 flex-1 flex-col nav:ml-60">
          <Topbar title={pageTitle} onToggle={() => setSidebarOpen(o => !o)} />
          <div className="mx-auto w-full max-w-[1180px] flex-1 px-4 pt-5 pb-[50px] nav:px-[34px] nav:pt-[30px] nav:pb-[60px]">
            {apiError && (
              <div className="mb-4 rounded-lg border border-warn bg-warn-soft px-4 py-2.5 text-sm text-ink">
                Aviso de sincronização: {apiError}
              </div>
            )}
            {content}
          </div>
        </div>
      </div>
      <Toast toast={toast} />
    </>
  );
}
