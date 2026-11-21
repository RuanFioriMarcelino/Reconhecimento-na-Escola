import { useCallback, useEffect, useState } from 'react';
import Icon from '../../icons/Icon.jsx';
import Avatar from '../../components/Avatar.jsx';
import CameraCaptura from '../../components/CameraCaptura.jsx';
import PaginationBar from '../../components/PaginationBar.jsx';
import { BiometriaPill, LogStatusPill, TipoPill } from '../../components/Pills.jsx';
import { PERSON_CONFIG, fmtMin } from '../../data/seed.js';
import { api } from '../../lib/api.js';
import AlertCard from '../alertas/AlertCard.jsx';

export default function PerfilPessoa({ tipo, id, liveTick = 0, onNavigate, showToast }) {
  const cfg = PERSON_CONFIG[tipo] || PERSON_CONFIG.aluno;

  const [p, setP] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyPagination, setHistoryPagination] = useState(null);
  const [relAlerts, setRelAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [histPage, setHistPage] = useState(1);

  const [editing, setEditing] = useState(false);
  const [showBioModal, setShowBioModal] = useState(false);
  const [bioError, setBioError] = useState('');
  const [bioSaving, setBioSaving] = useState(false);
  const [form, setForm] = useState({
    nome: '',
    documento: '',
    grupo: '',
    turno: '',
    contatoNome: '',
    contatoTelefone: '',
  });

  const loadPerson = useCallback(async () => {
    try {
      const data = await api.getPerson(id, { page: histPage, page_size: 15 });
      setP(data.person);
      setHistory(data.history || []);
      setHistoryPagination(data.historyPagination || null);
      setRelAlerts(data.alerts || []);
      setForm({
        nome: data.person.nome || '',
        documento: data.person.documento || '',
        grupo: data.person.grupo || '',
        turno: data.person.turno || '',
        contatoNome: data.person.contatoNome || '',
        contatoTelefone: data.person.contatoTelefone || '',
      });
    } catch {
      setP(null);
    } finally {
      setLoading(false);
    }
  }, [id, histPage]);

  useEffect(() => {
    setHistPage(1);
    setLoading(true);
  }, [id]);

  useEffect(() => {
    loadPerson();
  }, [loadPerson, liveTick]);

  if (loading && !p) {
    return <div className="card empty">Carregando perfil...</div>;
  }

  if (!p) {
    return (
      <div>
        <button className="back-link" onClick={() => onNavigate(tipo === 'aluno' ? 'alunos' : 'funcionarios')}>
          <Icon name="back" size={15} /> Voltar
        </button>
        <div className="card empty">Registro não encontrado no banco de dados.</div>
      </div>
    );
  }

  async function saveEdit(event) {
    event.preventDefault();
    try {
      const updated = await api.updatePerson(p.id, form);
      setP(updated);
      setEditing(false);
      showToast('Cadastro atualizado no PostgreSQL', 'check');
    } catch (error) {
      showToast(error.message || 'Erro ao atualizar cadastro.', 'triangle');
    }
  }

  async function handleSetStatus(nextStatus) {
    try {
      await api.setPersonStatus(p.id, nextStatus);
      setP(cur => ({ ...cur, status: nextStatus }));
      showToast(nextStatus === 'inativo' ? 'Cadastro desativado' : 'Cadastro reativado', 'check');
    } catch (error) {
      showToast(error.message || 'Erro ao alterar status.', 'triangle');
    }
  }

  async function handleEnrollFiles(files) {
    if (!files || files.length === 0) return;
    setBioSaving(true);
    setBioError('');
    try {
      const res = await api.enrollBiometrics(p.id, files);
      setShowBioModal(false);
      await loadPerson();
      showToast(`Biometria criptografada salva (qualidade ${Math.round(res.qualidade * 100)}%)`, 'check');
    } catch (error) {
      setBioError(error.message || 'Erro ao validar captura facial.');
    } finally {
      setBioSaving(false);
    }
  }

  async function handleRevokeBio() {
    try {
      await api.deleteBiometrics(p.id);
      await loadPerson();
      showToast('Biometria removida conforme LGPD', 'check');
    } catch (error) {
      showToast(error.message || 'Falha ao revogar biometria.', 'triangle');
    }
  }

  return (
    <div>
      <button className="back-link" onClick={() => onNavigate(tipo === 'aluno' ? 'alunos' : 'funcionarios')}>
        <Icon name="back" size={15} /> Voltar para {cfg.plural.toLowerCase()}
      </button>

      <div className="profile-head">
        <Avatar nome={p.nome} size={64} />
        <div>
          <h1>{p.nome}</h1>
          <div className="profile-meta">
            <TipoPill tipo={p.tipo} />
            <span>{p.grupo} · {p.turno}</span>
            <span>{cfg.documentoLabel} {p.documento}</span>
            <BiometriaPill cadastrada={p.biometriaCadastrada} qualidade={p.biometriaQualidade} />
            {p.status === 'inativo' && <span className="pill pill-neutral">Inativo</span>}
          </div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <button className="btn btn-primary" onClick={() => { setShowBioModal(v => !v); setBioError(''); }}>
            <Icon name="camera" size={15} /> {p.biometriaCadastrada ? 'Atualizar biometria' : 'Cadastrar biometria'}
          </button>
          {p.biometriaCadastrada && (
            <button className="btn btn-danger-ghost" onClick={handleRevokeBio}>
              Revogar biometria (LGPD)
            </button>
          )}
          <button className="btn btn-ghost" onClick={() => setEditing(true)}>
            <Icon name="edit" size={15} /> Editar
          </button>
          {p.status === 'ativo' ? (
            <button className="btn btn-danger-ghost" onClick={() => handleSetStatus('inativo')}>
              Desativar
            </button>
          ) : (
            <button className="btn btn-ghost" onClick={() => handleSetStatus('ativo')}>
              Reativar
            </button>
          )}
        </div>
      </div>

      {showBioModal && (
        <div className="card" style={{ padding: 20, marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h2 className="section-title" style={{ margin: 0 }}>Câmera de registro — {p.nome}</h2>
            <button className="btn btn-ghost" onClick={() => setShowBioModal(false)}>Fechar</button>
          </div>
          <CameraCaptura errorText={bioError} onCaptured={handleEnrollFiles} />
          {bioSaving && <p style={{ fontSize: 13, marginTop: 10 }}>Extraindo e criptografando vetor biométrico no servidor...</p>}
        </div>
      )}

      {editing && (
        <form className="card" style={{ padding: 18, marginBottom: 20 }} onSubmit={saveEdit}>
          <h2 className="section-title">Editar cadastro</h2>
          <div className="form-grid">
            {[
              ['nome', 'Nome completo'],
              ['documento', cfg.documentoLabel],
              ['grupo', cfg.grupoLabel],
              ['turno', 'Turno'],
              ['contatoNome', cfg.contatoNomeLabel],
              ['contatoTelefone', cfg.contatoTelefoneLabel],
            ].map(([key, label]) => (
              <div className="field" key={key}>
                <label>{label}</label>
                <input value={form[key]} onChange={e => setForm({ ...form, [key]: e.target.value })} required />
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
            <button className="btn btn-primary" type="submit"><Icon name="check" size={15} /> Salvar</button>
            <button className="btn btn-ghost" type="button" onClick={() => setEditing(false)}>Cancelar</button>
          </div>
        </form>
      )}

      <div className="grid-2">
        <div>
          <div className="section">
            <h2 className="section-title">Histórico real de passagens na portaria</h2>
            <div className="card">
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Data</th>
                      <th>Hora</th>
                      <th>Movimento</th>
                      <th>Portal</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.length ? (
                      history.map(h => (
                        <tr key={h.id}>
                          <td>{h.dataDia}</td>
                          <td style={{ fontFamily: 'var(--font-mono)' }}>{fmtMin(h.horaMin)}</td>
                          <td>{h.tipo === 'entrada' ? 'Entrada' : 'Saída'}</td>
                          <td>{h.local}</td>
                          <td><LogStatusPill status={h.status} /></td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={5} style={{ textAlign: 'center', color: 'var(--ink-faint)', padding: 24 }}>
                          Nenhuma passagem registrada até o momento.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
            {historyPagination && historyPagination.total > historyPagination.pageSize && (
              <PaginationBar pagination={historyPagination} onPageChange={setHistPage} />
            )}
          </div>

          <div className="section">
            <h2 className="section-title">Alertas relacionados</h2>
            {relAlerts.length ? (
              relAlerts.map(a => <AlertCard key={a.id} alert={a} onUpdateStatus={null} />)
            ) : (
              <div className="card empty" style={{ padding: 22 }}>Nenhum alerta para este registro.</div>
            )}
          </div>
        </div>

        <div>
          <div className="section">
            <h2 className="section-title">Dados cadastrais e conformidade LGPD</h2>
            <div className="card" style={{ padding: '16px 18px' }}>
              <div className="kv"><span>{cfg.dataLabel}</span><span>{p.dataRef}</span></div>
              <div className="kv"><span>{cfg.contatoNomeLabel}</span><span>{p.contatoNome}</span></div>
              <div className="kv"><span>{cfg.contatoTelefoneLabel}</span><span>{p.contatoTelefone}</span></div>
              <div className="kv"><span>Cadastrado em</span><span>{p.dataCadastro}</span></div>
              <div className="kv"><span>Turno</span><span>{p.turno}</span></div>
              <div className="kv">
                <span>Consentimento LGPD</span>
                <span>{p.consentimentoBiometrico ? 'Autorizado' : 'Pendente'}</span>
              </div>
              <div className="kv">
                <span>Presente agora</span>
                <span>{p.presenteAgora ? 'Sim (na escola)' : 'Não'}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
