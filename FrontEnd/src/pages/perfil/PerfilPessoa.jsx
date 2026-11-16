import { useState } from 'react';
import Icon from '../../icons/Icon.jsx';
import Avatar from '../../components/Avatar.jsx';
import { TipoPill } from '../../components/Pills.jsx';
import { PERSON_CONFIG, historicoPessoa } from '../../data/seed.js';
import AlertCard from '../alertas/AlertCard.jsx';

export default function PerfilPessoa({ tipo, id, people, alerts, onNavigate, onSetStatus, onEditPerson, showToast }) {
  const cfg = PERSON_CONFIG[tipo];
  const p = people.find(x => x.id === id && x.tipo === tipo);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState(() => ({
    nome: p?.nome || '', documento: p?.documento || '', grupo: p?.grupo || '',
    turno: p?.turno || '', contatoNome: p?.contatoNome || '', contatoTelefone: p?.contatoTelefone || '',
  }));
  if (!p) {
    return (
      <div>
        <button className="back-link" onClick={() => onNavigate(tipo === 'aluno' ? 'alunos' : 'funcionarios')}><Icon name="back" size={15} /> Voltar</button>
        <div className="card empty">Registro não encontrado neste protótipo.</div>
      </div>
    );
  }
  const hist = historicoPessoa(p.id);
  const relAlerts = alerts.filter(a => a.personId === p.id);
  async function saveEdit(event) {
    event.preventDefault();
    await onEditPerson(p.id, form);
    setEditing(false);
    showToast('Cadastro atualizado', 'check');
  }
  return (
    <div>
      <button className="back-link" onClick={() => onNavigate(tipo === 'aluno' ? 'alunos' : 'funcionarios')}><Icon name="back" size={15} /> Voltar para {cfg.plural.toLowerCase()}</button>
      <div className="profile-head">
        <Avatar nome={p.nome} size={64} />
        <div><h1>{p.nome}</h1>
          <div className="profile-meta">
            <TipoPill tipo={p.tipo} />
            <span>{p.grupo} · {p.turno}</span>
            <span>{cfg.documentoLabel} {p.documento}</span>
            {p.status === 'ativo'
              ? <span className="pill pill-good"><Icon name="check" size={11} /> Rosto cadastrado</span>
              : <span className="pill pill-neutral">Inativo</span>}
          </div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost" onClick={() => setEditing(true)}>
            <Icon name="edit" size={15} /> Editar</button>
          {p.status === 'ativo'
            ? <button className="btn btn-danger-ghost" onClick={() => { onSetStatus(p.id, 'inativo'); showToast('Cadastro desativado', 'check'); }}>Desativar</button>
            : <button className="btn btn-ghost" onClick={() => { onSetStatus(p.id, 'ativo'); showToast('Cadastro reativado', 'check'); }}>Reativar</button>}
        </div>
        {editing && <form className="card" style={{ padding: 18, marginBottom: 20 }} onSubmit={saveEdit}>
          <h2 className="section-title">Editar cadastro</h2>
          <div className="form-grid">
            {[
              ['nome', 'Nome completo'], ['documento', cfg.documentoLabel],
              ['grupo', cfg.grupoLabel], ['turno', 'Turno'],
              ['contatoNome', cfg.contatoNomeLabel], ['contatoTelefone', cfg.contatoTelefoneLabel],
            ].map(([key, label]) => <div className="field" key={key}>
              <label>{label}</label>
              <input value={form[key]} onChange={e => setForm({ ...form, [key]: e.target.value })} required />
            </div>)}
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
            <button className="btn btn-primary" type="submit"><Icon name="check" size={15} /> Salvar</button>
            <button className="btn btn-ghost" type="button" onClick={() => setEditing(false)}>Cancelar</button>
          </div>
        </form>}
      </div>
      <div className="grid-2">
        <div>
          <div className="section"><h2 className="section-title">Frequência recente</h2>
            <div className="card"><div className="table-wrap"><table>
              <thead><tr><th>Dia</th><th>Status</th><th>Entrada</th></tr></thead>
              <tbody>{hist.map(h => {
                const cls = h.status === 'presente' ? 'pill-good' : h.status === 'atraso' ? 'pill-warn' : 'pill-danger';
                const label = h.status === 'presente' ? 'Presente' : h.status === 'atraso' ? 'Atraso' : 'Falta';
                return <tr key={h.dia}><td>{h.dia}</td><td><span className={"pill " + cls}>{label}</span></td>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>{h.hora}</td></tr>;
              })}</tbody>
            </table></div></div>
          </div>
          <div className="section"><h2 className="section-title">Alertas relacionados</h2>
            {relAlerts.length
              ? relAlerts.map(a => <AlertCard key={a.id} alert={a} people={people} onResolver={null} />)
              : <div className="card empty" style={{ padding: 22 }}>Nenhum alerta para este registro.</div>}
          </div>
        </div>
        <div>
          <div className="section"><h2 className="section-title">Dados cadastrais</h2>
            <div className="card" style={{ padding: '16px 18px' }}>
              <div className="kv"><span>{cfg.dataLabel}</span><span>{p.dataRef}</span></div>
              <div className="kv"><span>{cfg.contatoNomeLabel}</span><span>{p.contatoNome}</span></div>
              <div className="kv"><span>{cfg.contatoTelefoneLabel}</span><span>{p.contatoTelefone}</span></div>
              <div className="kv"><span>Cadastrado em</span><span>{p.dataCadastro}</span></div>
              <div className="kv"><span>Turno</span><span>{p.turno}</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
