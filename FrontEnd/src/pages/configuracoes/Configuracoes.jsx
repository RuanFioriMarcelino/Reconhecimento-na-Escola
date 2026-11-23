import { useCallback, useEffect, useState } from 'react';
import Icon from '../../icons/Icon.jsx';
import PaginationBar from '../../components/PaginationBar.jsx';
import ToggleRow from './ToggleRow.jsx';
import { api } from '../../lib/api.js';

export default function Configuracoes({
  user,
  settings,
  onSaveSettings,
  turmas = [],
  turnos = [],
  dispositivos = [],
  onAddClass,
  onRefresh,
  showToast,
}) {
  const [local, setLocal] = useState(settings);
  const [savingSettings, setSavingSettings] = useState(false);

  const [className, setClassName] = useState('');
  const [year, setYear] = useState(new Date().getFullYear());
  const [turnoId, setTurnoId] = useState('');
  const [turnoName, setTurnoName] = useState('');
  const [turnoStart, setTurnoStart] = useState('07:00');
  const [turnoLimit, setTurnoLimit] = useState('07:20');

  const [devNome, setDevNome] = useState('');
  const [devPortal, setDevPortal] = useState('');
  const [devSentido, setDevSentido] = useState('auto');
  const [newApiKey, setNewApiKey] = useState('');

  const [auditLogs, setAuditLogs] = useState([]);
  const [auditPage, setAuditPage] = useState(1);
  const [auditOp, setAuditOp] = useState('');
  const [auditSensivel, setAuditSensivel] = useState('');
  const [auditPagination, setAuditPagination] = useState(null);
  const isGestor = user?.papel === 'admin' || user?.papel === 'coordenacao';

  useEffect(() => {
    setLocal(settings);
  }, [settings]);

  const fetchAudit = useCallback(async () => {
    if (!isGestor) return;
    try {
      const data = await api.getAuditLogs({
        page: auditPage,
        page_size: 20,
        operacao: auditOp,
        sensivel: auditSensivel,
      });
      setAuditLogs(data.items || data.logs || []);
      setAuditPagination(data.pagination || null);
    } catch {
      setAuditLogs([]);
    }
  }, [isGestor, auditPage, auditOp, auditSensivel]);

  useEffect(() => {
    fetchAudit();
  }, [fetchAudit]);

  async function handleSaveSettings() {
    setSavingSettings(true);
    try {
      await onSaveSettings(local);
    } catch (error) {
      showToast(error.message || 'Erro ao salvar configurações.', 'triangle');
    } finally {
      setSavingSettings(false);
    }
  }

  async function handleCreateDevice(e) {
    e.preventDefault();
    try {
      const created = await api.createDevice({ nome: devNome, portal: devPortal, sentidoPadrao: devSentido });
      setNewApiKey(`${created.nome} -> ${created.apiKey}`);
      setDevNome('');
      setDevPortal('');
      await onRefresh();
      showToast('Dispositivo de portaria criado! Copie a chave agora.', 'check');
    } catch (error) {
      showToast(error.message || 'Erro ao criar dispositivo.', 'triangle');
    }
  }

  async function handleToggleDevice(dev) {
    try {
      await api.updateDevice(dev.id, { ativo: !dev.ativo });
      await onRefresh();
      showToast(`Câmera ${!dev.ativo ? 'ativada' : 'desativada'}`, 'check');
    } catch (error) {
      showToast(error.message || 'Erro ao atualizar dispositivo.', 'triangle');
    }
  }

  async function handleRotateKey(dev) {
    try {
      const updated = await api.updateDevice(dev.id, { rotacionarChave: true });
      setNewApiKey(`${updated.nome} (nova chave) -> ${updated.apiKey}`);
      await onRefresh();
      showToast('Chave do dispositivo rotacionada.', 'check');
    } catch (error) {
      showToast(error.message || 'Erro ao rotacionar chave.', 'triangle');
    }
  }

  async function handleChangeSentido(dev, sentido) {
    try {
      await api.updateDevice(dev.id, { sentidoPadrao: sentido });
      await onRefresh();
      showToast('Sentido padrão atualizado', 'check');
    } catch (error) {
      showToast(error.message || 'Erro ao alterar sentido.', 'triangle');
    }
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Configurações e segurança</h1>
          <p>Regras de entrada/saída passiva, câmeras de portaria e trilha de auditoria LGPD</p>
        </div>
        {isGestor && (
          <button className="btn btn-primary" disabled={savingSettings} onClick={handleSaveSettings}>
            <Icon name="check" size={16} /> {savingSettings ? 'Salvando...' : 'Salvar configurações'}
          </button>
        )}
      </div>

      {!isGestor && (
        <div role="status" className="mb-4 rounded-lg border border-line bg-surface-alt px-4 py-2.5 text-sm text-ink-soft">
          Modo somente leitura: apenas perfis de <strong>Administração</strong> ou <strong>Coordenação</strong> podem alterar parâmetros, câmeras de portaria e turmas.
        </div>
      )}

      <div className="grid-2">
        <div className="section" style={{ marginBottom: 0 }}>
          <h2 className="section-title">Horários e motor passivo</h2>
          <div className="card" style={{ padding: 18 }}>
            <div className="field" style={{ marginBottom: 12 }}>
              <label>Nome da instituição</label>
              <input disabled={!isGestor} value={local.nomeEscola || ''} onChange={e => setLocal({ ...local, nomeEscola: e.target.value })} />
            </div>
            <div className="form-grid">
              <div className="field">
                <label>Limite entrada — Manhã</label>
                <input disabled={!isGestor} type="time" value={local.limiteManha} onChange={e => setLocal({ ...local, limiteManha: e.target.value })} />
              </div>
              <div className="field">
                <label>Limite entrada — Tarde</label>
                <input disabled={!isGestor} type="time" value={local.limiteTarde} onChange={e => setLocal({ ...local, limiteTarde: e.target.value })} />
              </div>
              <div className="field">
                <label>Saída normal — Manhã</label>
                <input disabled={!isGestor} type="time" value={local.saidaManha || '11:30'} onChange={e => setLocal({ ...local, saidaManha: e.target.value })} />
              </div>
              <div className="field">
                <label>Saída normal — Tarde</label>
                <input disabled={!isGestor} type="time" value={local.saidaTarde || '17:30'} onChange={e => setLocal({ ...local, saidaTarde: e.target.value })} />
              </div>
              <div className="field">
                <label>Cooldown anti-duplicidade (seg)</label>
                <input
                  disabled={!isGestor}
                  type="number"
                  min={5}
                  max={600}
                  value={local.cooldownSegundos ?? 45}
                  onChange={e => setLocal({ ...local, cooldownSegundos: e.target.value === '' ? '' : Number(e.target.value) })}
                />
              </div>
              <div className="field">
                <label>Permanência mín. p/ saída (min)</label>
                <input
                  disabled={!isGestor}
                  type="number"
                  min={1}
                  max={120}
                  value={local.tempoMinimoPermanenciaMin ?? 2}
                  onChange={e => setLocal({ ...local, tempoMinimoPermanenciaMin: e.target.value === '' ? '' : Number(e.target.value) })}
                />
              </div>
              <div className="field">
                <label>Limiar de confiança SFace (0.25–0.85)</label>
                <input
                  disabled={!isGestor}
                  type="number"
                  step="0.01"
                  min={0.25}
                  max={0.85}
                  value={local.limiarConfianca ?? 0.38}
                  onChange={e => setLocal({ ...local, limiarConfianca: e.target.value === '' ? '' : Number(e.target.value) })}
                />
              </div>
              <div className="field">
                <label>Retenção LGPD de logs (dias)</label>
                <input
                  disabled={!isGestor}
                  type="number"
                  min={30}
                  max={3650}
                  value={local.retencaoLogsDias ?? 365}
                  onChange={e => setLocal({ ...local, retencaoLogsDias: e.target.value === '' ? '' : Number(e.target.value) })}
                />
              </div>
            </div>
          </div>
        </div>

        <div className="section" style={{ marginBottom: 0 }}>
          <h2 className="section-title">Avisos automáticos da portaria</h2>
          <div className="card" style={{ padding: '6px 18px' }}>
            <ToggleRow
              disabled={!isGestor}
              title="Modo passivo contínuo"
              desc="Registrar entradas/saídas sem exigir autorização manual na portaria"
              on={Boolean(local.modoPassivo)}
              onToggle={() => setLocal({ ...local, modoPassivo: !local.modoPassivo })}
            />
            <ToggleRow
              disabled={!isGestor}
              title="Atrasos na entrada"
              desc="Gerar aviso quando o aluno passar após o limite do turno"
              on={Boolean(local.notifAtraso)}
              onToggle={() => setLocal({ ...local, notifAtraso: !local.notifAtraso })}
            />
            <ToggleRow
              disabled={!isGestor}
              title="Saída antecipada"
              desc="Gerar aviso se o aluno sair antes do término das aulas"
              on={Boolean(local.notifSaidaAntecipada)}
              onToggle={() => setLocal({ ...local, notifSaidaAntecipada: !local.notifSaidaAntecipada })}
            />
            <ToggleRow
              disabled={!isGestor}
              title="Ausências"
              desc="Avisar quando não houver registro de entrada"
              on={Boolean(local.notifAusencia)}
              onToggle={() => setLocal({ ...local, notifAusencia: !local.notifAusencia })}
            />
            <ToggleRow
              disabled={!isGestor}
              title="Pessoas não cadastradas"
              desc="Gerar alerta quando um rosto desconhecido passar na portaria"
              on={Boolean(local.notifNaoReconhecido)}
              onToggle={() => setLocal({ ...local, notifNaoReconhecido: !local.notifNaoReconhecido })}
            />
          </div>
        </div>
      </div>

      <div className="section">
        <h2 className="section-title">Câmeras e terminais de portaria (autenticação por X-Portaria-Key)</h2>

        {newApiKey && (
          <div className="mb-3 rounded-lg border border-good bg-good-soft px-4 py-3 text-xs">
            <strong>Chave gerada (copie agora — não será exibida novamente):</strong>{' '}
            <code style={{ fontFamily: 'var(--font-mono)', userSelect: 'all' }}>{newApiKey}</code>
          </div>
        )}

        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Dispositivo</th>
                  <th>Portal</th>
                  <th>Sentido</th>
                  <th>Prefixo</th>
                  <th>Status</th>
                  <th>Telemetria</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {dispositivos.map(dev => (
                  <tr key={dev.id}>
                    <td><strong>{dev.nome}</strong></td>
                    <td>{dev.portal}</td>
                    <td>
                      <select
                        disabled={!isGestor}
                        value={dev.sentidoPadrao}
                        onChange={e => handleChangeSentido(dev, e.target.value)}
                        style={{ padding: '4px 8px', fontSize: 12 }}
                      >
                        <option value="auto">Automático</option>
                        <option value="entrada">Somente Entrada</option>
                        <option value="saida">Somente Saída</option>
                      </select>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{dev.apiKeyPrefixo}...</td>
                    <td>
                      {!dev.ativo ? (
                        <span className="pill pill-neutral">Desativado</span>
                      ) : dev.online ? (
                        <span className="pill pill-good"><Icon name="check" size={11} /> Online</span>
                      ) : (
                        <span className="pill pill-warn">Offline</span>
                      )}
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--ink-soft)' }}>
                      {dev.telemetria?.fps ? `${dev.telemetria.fps} FPS · ${dev.telemetria.aiMs || 0}ms` : 'Sem heartbeat'}
                    </td>
                    <td>
                      {isGestor ? (
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button className="btn btn-ghost" style={{ padding: '4px 8px', fontSize: 12 }} onClick={() => handleToggleDevice(dev)}>
                            {dev.ativo ? 'Desativar' : 'Ativar'}
                          </button>
                          <button className="btn btn-ghost" style={{ padding: '4px 8px', fontSize: 12 }} onClick={() => handleRotateKey(dev)}>
                            Nova chave
                          </button>
                        </div>
                      ) : (
                        <span style={{ fontSize: 12, color: 'var(--ink-faint)' }}>Somente leitura</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {isGestor && (
        <form className="card" style={{ padding: 18, marginTop: 12 }} onSubmit={handleCreateDevice}>
          <h3 className="section-title">Cadastrar novo terminal de portaria</h3>
          <div className="form-grid" style={{ gridTemplateColumns: '1fr 1fr 180px auto', alignItems: 'end' }}>
            <div className="field">
              <label>Nome do dispositivo</label>
              <input value={devNome} onChange={e => setDevNome(e.target.value)} required placeholder="Portaria Fundos - Câmera 03" />
            </div>
            <div className="field">
              <label>Portal</label>
              <input value={devPortal} onChange={e => setDevPortal(e.target.value)} required placeholder="Portão dos fundos" />
            </div>
            <div className="field">
              <label>Sentido padrão</label>
              <select value={devSentido} onChange={e => setDevSentido(e.target.value)}>
                <option value="auto">Automático</option>
                <option value="entrada">Somente Entrada</option>
                <option value="saida">Somente Saída</option>
              </select>
            </div>
            <button type="submit" className="btn btn-ghost"><Icon name="check" size={15} /> Gerar dispositivo</button>
          </div>
        </form>
        )}
      </div>

      <div className="section">
        <h2 className="section-title">Turmas e turnos</h2>
        {isGestor && (
        <div className="grid-2">
          <form
            className="card"
            style={{ padding: 18 }}
            onSubmit={async e => {
              e.preventDefault();
              try {
                await onAddClass({ tipo: 'turno', nome: turnoName, inicio: turnoStart, limiteEntrada: turnoLimit });
                setTurnoName('');
                showToast('Turno cadastrado', 'check');
              } catch (error) {
                showToast(error.message || 'Erro ao cadastrar turno.', 'triangle');
              }
            }}
          >
            <h3 className="section-title">Novo turno</h3>
            <div className="field"><label>Nome</label><input value={turnoName} onChange={e => setTurnoName(e.target.value)} required placeholder="Noite" /></div>
            <div className="form-grid">
              <div className="field"><label>Início</label><input type="time" value={turnoStart} onChange={e => setTurnoStart(e.target.value)} required /></div>
              <div className="field"><label>Limite de entrada</label><input type="time" value={turnoLimit} onChange={e => setTurnoLimit(e.target.value)} required /></div>
            </div>
            <button className="btn btn-ghost" style={{ marginTop: 12 }}><Icon name="check" size={15} /> Cadastrar turno</button>
          </form>

          <form
            className="card"
            style={{ padding: 18 }}
            onSubmit={async e => {
              e.preventDefault();
              try {
                await onAddClass({ tipo: 'turma', nome: className, anoLetivo: year, turnoId });
                setClassName('');
                showToast('Turma cadastrada', 'check');
              } catch (error) {
                showToast(error.message || 'Erro ao cadastrar turma.', 'triangle');
              }
            }}
          >
            <h3 className="section-title">Nova turma</h3>
            <div className="field"><label>Nome</label><input value={className} onChange={e => setClassName(e.target.value)} required placeholder="8º A" /></div>
            <div className="form-grid">
              <div className="field"><label>Ano letivo</label><input type="number" value={year} onChange={e => setYear(e.target.value)} required /></div>
              <div className="field">
                <label>Turno</label>
                <select value={turnoId} onChange={e => setTurnoId(e.target.value)} required>
                  <option value="">Selecione</option>
                  {turnos.map(t => <option key={t.id} value={t.id}>{t.nome}</option>)}
                </select>
              </div>
            </div>
            <button className="btn btn-ghost" style={{ marginTop: 12 }}><Icon name="check" size={15} /> Cadastrar turma</button>
          </form>
        </div>
        )}
        <div className="card" style={{ marginTop: 12 }}>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Turma</th><th>Ano</th><th>Turno</th></tr></thead>
              <tbody>{turmas.map(t => <tr key={t.id}><td>{t.nome}</td><td>{t.anoLetivo}</td><td>{t.turno}</td></tr>)}</tbody>
            </table>
          </div>
        </div>
      </div>

      {isGestor && (
        <div className="section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 12 }}>
            <h2 className="section-title" style={{ margin: 0 }}>Trilha de auditoria (LGPD — paginada no PostgreSQL)</h2>
            <div style={{ display: 'flex', gap: 8 }}>
              <select value={auditOp} onChange={e => { setAuditOp(e.target.value); setAuditPage(1); }} style={{ padding: '5px 10px', fontSize: 12 }}>
                <option value="">Todas operações</option>
                {['INSERT', 'UPDATE', 'DELETE', 'SELECT', 'AUTH', 'SYNC'].map(op => (
                  <option key={op} value={op}>{op}</option>
                ))}
              </select>
              <select value={auditSensivel} onChange={e => { setAuditSensivel(e.target.value); setAuditPage(1); }} style={{ padding: '5px 10px', fontSize: 12 }}>
                <option value="">Todos os níveis</option>
                <option value="1">Apenas LGPD (sensível)</option>
              </select>
            </div>
          </div>

          <div className="card">
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Data/Hora</th><th>Usuário / Origem</th><th>Operação</th><th>Tabela</th><th>Chave</th><th>Sensível</th></tr>
                </thead>
                <tbody>
                  {auditLogs.map(log => (
                    <tr key={log.id}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                        {new Date(log.ocorridoEm).toLocaleString('pt-BR')}
                      </td>
                      <td>{log.usuario || '—'}</td>
                      <td><span className="pill pill-neutral">{log.operacao}</span></td>
                      <td>{log.tabela}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{log.chave || '—'}</td>
                      <td>{log.sensivel ? <span className="pill pill-warn">LGPD</span> : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {auditPagination && (
            <PaginationBar pagination={auditPagination} onPageChange={setAuditPage} />
          )}
        </div>
      )}
    </div>
  );
}
