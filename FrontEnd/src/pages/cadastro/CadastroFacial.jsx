import { useState } from 'react';
import Icon from '../../icons/Icon.jsx';
import { PERSON_CONFIG, turnoDaTurma, avatarColor, initials } from '../../data/seed.js';

export default function CadastroFacial({ tipoInicial, onSubmitPerson, onNavigate, showToast }) {
  const [tipo, setTipo] = useState(tipoInicial || 'aluno');
  const cfg = PERSON_CONFIG[tipo];
  const [nome, setNome] = useState('');
  const [documento, setDocumento] = useState('');
  const [grupo, setGrupo] = useState('');
  const [turnoManual, setTurnoManual] = useState('Manhã');
  const [dataRef, setDataRef] = useState('');
  const [contatoNome, setContatoNome] = useState('');
  const [contatoTelefone, setContatoTelefone] = useState('');
  const [capturaFeita, setCapturaFeita] = useState(false);
  const [capturando, setCapturando] = useState(false);

  function trocarTipo(t) {
    setTipo(t); setNome(''); setDocumento(''); setGrupo(''); setDataRef('');
    setContatoNome(''); setContatoTelefone(''); setCapturaFeita(false);
  }
  function simularCaptura() {
    setCapturando(true);
    setTimeout(() => { setCapturaFeita(true); setCapturando(false); }, 900);
  }
  function submit(e) {
    e.preventDefault();
    if (!nome || !documento || !grupo || !contatoNome || !contatoTelefone) {
      showToast('Preencha todos os campos obrigatórios', 'triangle'); return;
    }
    if (!capturaFeita) {
      showToast('Simule a captura facial antes de concluir', 'triangle'); return;
    }
    const turno = tipo === 'aluno' ? turnoDaTurma(grupo) : turnoManual;
    const novo = {
      tipo, nome, documento, grupo, turno, status: 'ativo',
      contatoNome, contatoTelefone, dataCadastro: '16/09/2026', dataRef: dataRef || '—'
    };
    const id = onSubmitPerson(novo);
    showToast(cfg.singular + ' cadastrado(a) com sucesso', 'check');
    onNavigate('pessoa', tipo, id);
  }

  return (
    <div>
      <div className="page-head"><div><h1>Cadastro facial</h1><p>Registre uma pessoa e capture o rosto para reconhecimento na portaria</p></div></div>
      <div className="segmented">
        <button className={tipo === 'aluno' ? 'active' : ''} onClick={() => trocarTipo('aluno')}><Icon name="users" size={15} /> Aluno</button>
        <button className={tipo === 'funcionario' ? 'active' : ''} onClick={() => trocarTipo('funcionario')}><Icon name="briefcase" size={15} /> Funcionário</button>
      </div>
      <form onSubmit={submit}>
        <div className="grid-2">
          <div className="card" style={{ padding: 22 }}>
            <h2 className="section-title">Dados {tipo === 'aluno' ? 'do aluno' : 'do(a) funcionário(a)'}</h2>
            <div className="form-grid">
              <div className="field full"><label>Nome completo</label>
                <input value={nome} onChange={e => setNome(e.target.value)} required placeholder="Ex.: Maria Eduarda Souza" /></div>
              <div className="field"><label>{cfg.documentoLabel}</label>
                <input value={documento} onChange={e => setDocumento(e.target.value)} required placeholder={cfg.documentoPlaceholder} /></div>
              <div className="field"><label>{cfg.dataLabel}</label>
                <input type="date" value={dataRef} onChange={e => setDataRef(e.target.value)} /></div>
              <div className="field"><label>{cfg.grupoLabel}</label>
                <select value={grupo} onChange={e => setGrupo(e.target.value)} required>
                  <option value="">Selecione</option>
                  {cfg.grupoOptions.map(g => <option key={g} value={g}>{g}</option>)}
                </select></div>
              <div className="field"><label>Turno</label>
                {tipo === 'aluno'
                  ? <input disabled value={grupo ? turnoDaTurma(grupo) : 'Definido pela turma'} />
                  : <select value={turnoManual} onChange={e => setTurnoManual(e.target.value)}>
                      <option>Manhã</option><option>Tarde</option><option>Integral</option>
                    </select>}
              </div>
              <div className="field"><label>{cfg.contatoNomeLabel}</label>
                <input value={contatoNome} onChange={e => setContatoNome(e.target.value)} required placeholder="Nome completo" /></div>
              <div className="field"><label>{cfg.contatoTelefoneLabel}</label>
                <input value={contatoTelefone} onChange={e => setContatoTelefone(e.target.value)} required placeholder="(00) 90000-0000" /></div>
            </div>
          </div>
          <div className="card" style={{ padding: 22 }}>
            <h2 className="section-title">Captura facial</h2>
            <div className="capture-box">
              <div className="capture-preview" style={capturaFeita ? { background: avatarColor(nome || '?'), border: 'none', color: '#fff' } : {}}>
                {capturaFeita ? initials(nome || '??') : <Icon name="camera" size={30} />}
              </div>
              <div className="capture-status">
                {capturando ? 'Capturando e processando o rosto...'
                  : capturaFeita ? <span><Icon name="check" size={13} /> Rosto capturado com sucesso. Pronto para reconhecimento na portaria.</span>
                  : 'Posicione a pessoa em frente à câmera da portaria e simule a captura.'}
              </div>
              <button type="button" className="btn btn-ghost" disabled={capturando} onClick={simularCaptura}>
                <Icon name="scan" size={16} /> {capturaFeita ? 'Capturar novamente' : 'Simular captura'}
              </button>
            </div>
            <p style={{ fontSize: 12, color: 'var(--ink-faint)', marginTop: 14 }}>
              Neste protótipo a captura é simulada. Na versão final, esta etapa se conecta à câmera da portaria e ao motor de reconhecimento facial.
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
          <button type="submit" className="btn btn-primary"><Icon name="check" size={16} /> Concluir cadastro</button>
          <button type="button" className="btn btn-ghost" onClick={() => onNavigate(tipo === 'aluno' ? 'alunos' : 'funcionarios')}>Cancelar</button>
        </div>
      </form>
    </div>
  );
}
