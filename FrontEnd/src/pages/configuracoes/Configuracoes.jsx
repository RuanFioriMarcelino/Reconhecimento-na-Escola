import { useState } from 'react';
import Icon from '../../icons/Icon.jsx';
import ToggleRow from './ToggleRow.jsx';

export default function Configuracoes({ settings, onChange, showToast }) {
  const [local, setLocal] = useState(settings);
  return (
    <div>
      <div className="page-head"><div><h1>Configurações</h1><p>Regras de horário e notificações do reconhecimento facial</p></div></div>
      <div className="grid-2">
        <div className="section" style={{ marginBottom: 0 }}><h2 className="section-title">Horários limite</h2>
          <div className="card" style={{ padding: 18 }}>
            <div className="field" style={{ marginBottom: 14 }}><label>Limite de entrada — turno da manhã</label>
              <input type="time" value={local.limiteManha} onChange={e => setLocal({ ...local, limiteManha: e.target.value })} /></div>
            <div className="field"><label>Limite de entrada — turno da tarde</label>
              <input type="time" value={local.limiteTarde} onChange={e => setLocal({ ...local, limiteTarde: e.target.value })} /></div>
          </div>
        </div>
        <div className="section" style={{ marginBottom: 0 }}><h2 className="section-title">Notificações</h2>
          <div className="card" style={{ padding: '6px 18px' }}>
            <ToggleRow title="Atrasos" desc="Avisar a cada atraso registrado" on={local.notifAtraso}
              onToggle={() => setLocal({ ...local, notifAtraso: !local.notifAtraso })} />
            <ToggleRow title="Ausências" desc="Avisar quando não houver entrada até o limite" on={local.notifAusencia}
              onToggle={() => setLocal({ ...local, notifAusencia: !local.notifAusencia })} />
            <ToggleRow title="Rostos não reconhecidos" desc="Avisar sobre tentativas de acesso não identificadas" on={local.notifNaoReconhecido}
              onToggle={() => setLocal({ ...local, notifNaoReconhecido: !local.notifNaoReconhecido })} />
          </div>
        </div>
      </div>
      <div className="section"><h2 className="section-title">Unidades de captura</h2>
        <div className="card"><div className="table-wrap"><table>
          <thead><tr><th>Local</th><th>Tipo</th><th>Status</th></tr></thead>
          <tbody>
            <tr><td>Portaria principal</td><td>Câmera de entrada</td><td><span className="pill pill-good"><Icon name="check" size={11} /> Online</span></td></tr>
            <tr><td>Catraca lateral</td><td>Câmera de entrada</td><td><span className="pill pill-good"><Icon name="check" size={11} /> Online</span></td></tr>
            <tr><td>Pátio coberto</td><td>Câmera de saída</td><td><span className="pill pill-neutral">Manutenção</span></td></tr>
          </tbody>
        </table></div></div>
      </div>
      <button className="btn btn-primary" onClick={() => { onChange(local); showToast('Configurações salvas', 'check'); }}>
        <Icon name="check" size={16} /> Salvar alterações</button>
    </div>
  );
}
