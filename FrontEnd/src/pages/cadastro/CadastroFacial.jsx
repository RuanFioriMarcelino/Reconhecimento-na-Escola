import { useState } from 'react';
import Icon from '../../icons/Icon.jsx';
import CameraCaptura from '../../components/CameraCaptura.jsx';
import { PERSON_CONFIG } from '../../data/seed.js';

export default function CadastroFacial({ tipoInicial, turmas = [], onSubmitPerson, onNavigate, showToast }) {
  const [tipo, setTipo] = useState(tipoInicial || 'aluno');
  const cfg = PERSON_CONFIG[tipo];
  const [nome, setNome] = useState('');
  const [documento, setDocumento] = useState('');
  const [grupo, setGrupo] = useState('');
  const [turmaId, setTurmaId] = useState('');
  const [turnoManual, setTurnoManual] = useState('Manhã');
  const [dataRef, setDataRef] = useState('');
  const [contatoNome, setContatoNome] = useState('');
  const [contatoTelefone, setContatoTelefone] = useState('');
  const [responsavelCpf, setResponsavelCpf] = useState('');
  const [consentimento, setConsentimento] = useState(false);
  const [faceFiles, setFaceFiles] = useState([]);
  const [saving, setSaving] = useState(false);
  const [bioError, setBioError] = useState('');
  const [savedPersonId, setSavedPersonId] = useState(null);

  const selectedTurma = turmas.find(t => String(t.id) === String(turmaId));
  const grupoOptions = tipo === 'aluno' && turmas.length > 0 ? turmas : cfg.grupoOptions;

  function trocarTipo(t) {
    setTipo(t);
    setNome('');
    setDocumento('');
    setGrupo('');
    setTurmaId('');
    setDataRef('');
    setContatoNome('');
    setContatoTelefone('');
    setResponsavelCpf('');
    setConsentimento(false);
    setFaceFiles([]);
    setBioError('');
    setSavedPersonId(null);
  }

  async function submit(e) {
    e.preventDefault();
    setBioError('');
    const finalGrupo = tipo === 'aluno' && selectedTurma ? selectedTurma.nome : grupo;
    const finalTurno = tipo === 'aluno' && selectedTurma ? selectedTurma.turno : turnoManual;

    if (!nome || !documento || !finalGrupo || !contatoNome || !contatoTelefone) {
      showToast('Preencha todos os campos obrigatórios', 'triangle');
      return;
    }
    if (faceFiles.length > 0 && !consentimento) {
      showToast('Confirme o consentimento biométrico (LGPD) antes de enviar a face.', 'triangle');
      return;
    }

    setSaving(true);
    let createdId = savedPersonId;
    try {
      const novo = {
        tipo,
        nome,
        documento,
        grupo: finalGrupo,
        turmaId: tipo === 'aluno' && selectedTurma ? selectedTurma.id : null,
        turno: finalTurno,
        status: 'ativo',
        contatoNome,
        contatoTelefone,
        responsavelCpf,
        consentimentoBiometrico: consentimento,
        consentimentoResponsavel: contatoNome,
        dataRef: dataRef || '—',
      };
      // Primeiro cria a pessoa se ainda não foi criada; se falhar na biometria, preserva o ID salvo
      createdId = await onSubmitPerson(novo, faceFiles, savedPersonId);
      showToast(`${cfg.singular} cadastrado(a) com sucesso!`, 'check');
      onNavigate('pessoa', tipo, createdId);
    } catch (error) {
      const msg = error.message || 'Erro ao salvar cadastro.';
      if (error.savedPersonId) {
        setSavedPersonId(error.savedPersonId);
      } else if (createdId && !savedPersonId) {
        setSavedPersonId(createdId);
      }
      setBioError(msg);
      showToast(msg, 'triangle');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Cadastro e registro biométrico</h1>
          <p>Estação de registro dedicada: cadastra dados no PostgreSQL e vetor facial criptografado (AES-256-GCM)</p>
        </div>
      </div>

      <div className="segmented">
        <button type="button" className={tipo === 'aluno' ? 'active' : ''} onClick={() => trocarTipo('aluno')}>
          <Icon name="users" size={15} /> Aluno
        </button>
        <button type="button" className={tipo === 'funcionario' ? 'active' : ''} onClick={() => trocarTipo('funcionario')}>
          <Icon name="briefcase" size={15} /> Funcionário
        </button>
      </div>

      {savedPersonId && (
        <div className="mb-4 rounded-lg border border-warn bg-warn-soft px-4 py-2.5 text-sm">
          Pessoa já salva no banco (<strong>{savedPersonId}</strong>). Ajuste a captura facial abaixo e clique em Concluir sem duplicar o cadastro.
        </div>
      )}

      <form onSubmit={submit}>
        <div className="grid-2">
          <div className="card" style={{ padding: 22 }}>
            <h2 className="section-title">Dados {tipo === 'aluno' ? 'do aluno' : 'do(a) funcionário(a)'}</h2>
            <div className="form-grid">
              <div className="field full">
                <label>Nome completo</label>
                <input value={nome} onChange={e => setNome(e.target.value)} required disabled={Boolean(savedPersonId)} placeholder="Ex.: Maria Eduarda Souza" />
              </div>
              <div className="field">
                <label>{cfg.documentoLabel}</label>
                <input value={documento} onChange={e => setDocumento(e.target.value)} required disabled={Boolean(savedPersonId)} placeholder={cfg.documentoPlaceholder} />
              </div>
              <div className="field">
                <label>{cfg.dataLabel}</label>
                <input type="date" value={dataRef} onChange={e => setDataRef(e.target.value)} disabled={Boolean(savedPersonId)} />
              </div>
              <div className="field">
                <label>{cfg.grupoLabel}</label>
                {tipo === 'aluno' && turmas.length > 0 ? (
                  <select
                    value={turmaId}
                    disabled={Boolean(savedPersonId)}
                    onChange={e => {
                      setTurmaId(e.target.value);
                      const found = turmas.find(t => String(t.id) === e.target.value);
                      setGrupo(found ? found.nome : '');
                    }}
                    required
                  >
                    <option value="">Selecione a turma</option>
                    {grupoOptions.map(t => (
                      <option key={t.id} value={t.id}>
                        {t.nome} ({t.turno})
                      </option>
                    ))}
                  </select>
                ) : (
                  <select value={grupo} onChange={e => setGrupo(e.target.value)} required disabled={Boolean(savedPersonId)}>
                    <option value="">Selecione</option>
                    {cfg.grupoOptions.map(g => (
                      <option key={g} value={g}>{g}</option>
                    ))}
                  </select>
                )}
              </div>
              <div className="field">
                <label>Turno</label>
                {tipo === 'aluno' ? (
                  <input disabled value={selectedTurma ? selectedTurma.turno : 'Definido pela turma'} />
                ) : (
                  <select value={turnoManual} onChange={e => setTurnoManual(e.target.value)} disabled={Boolean(savedPersonId)}>
                    <option>Manhã</option>
                    <option>Tarde</option>
                    <option>Integral</option>
                  </select>
                )}
              </div>
              <div className="field">
                <label>{cfg.contatoNomeLabel}</label>
                <input value={contatoNome} onChange={e => setContatoNome(e.target.value)} required disabled={Boolean(savedPersonId)} placeholder="Nome completo" />
              </div>
              <div className="field">
                <label>{cfg.contatoTelefoneLabel}</label>
                <input value={contatoTelefone} onChange={e => setContatoTelefone(e.target.value)} required disabled={Boolean(savedPersonId)} placeholder="(00) 90000-0000" />
              </div>
              {tipo === 'aluno' && (
                <div className="field full">
                  <label>CPF do responsável (opcional — criptografado LGPD)</label>
                  <input value={responsavelCpf} onChange={e => setResponsavelCpf(e.target.value)} disabled={Boolean(savedPersonId)} placeholder="000.000.000-00" />
                </div>
              )}
            </div>
          </div>

          <div className="card" style={{ padding: 22 }}>
            <h2 className="section-title">Câmera de registro biométrico</h2>
            <CameraCaptura
              errorText={bioError}
              onCaptured={files => {
                setBioError('');
                setFaceFiles(files);
              }}
            />

            <label style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginTop: 16, fontSize: 12.5, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={consentimento}
                onChange={e => setConsentimento(e.target.checked)}
                style={{ width: 'auto', marginTop: 2 }}
              />
              <span>
                <strong>Termo LGPD:</strong> Confirmo o consentimento expresso para extração do vetor biométrico facial. Nenhuma fotografia é armazenada no servidor ou nas câmeras da portaria.
              </span>
            </label>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            <Icon name="check" size={16} /> {saving ? 'Processando e criptografando...' : 'Concluir cadastro'}
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => onNavigate(tipo === 'aluno' ? 'alunos' : 'funcionarios')}>
            Cancelar
          </button>
        </div>
      </form>
    </div>
  );
}
