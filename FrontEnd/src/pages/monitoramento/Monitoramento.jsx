import { useState } from 'react';
import Icon from '../../icons/Icon.jsx';
import { cx } from '../../lib/cx.js';
import MonitoramentoRow from './MonitoramentoRow.jsx';

const FIELD_BASE =
  'rounded-[7px] border border-line bg-surface font-body text-[13.5px] ' +
  'leading-[normal] text-ink focus:border-primary focus:outline-none';

const SEARCH_INPUT = cx(FIELD_BASE, 'w-full pl-[34px] pr-3 py-[9px]');
const SELECT = cx(FIELD_BASE, 'w-full max-w-[190px] px-3 py-[9px]');

export default function Monitoramento({ people, logs, onNavigate }) {
  const [busca, setBusca] = useState('');
  const [tipoPessoa, setTipoPessoa] = useState('');
  const [tipoEvento, setTipoEvento] = useState('');

  const lista = logs
    .filter(l => {
      const p = l.personId ? people.find(x => x.id === l.personId) : null;
      return (
        (!busca || (p && p.nome.toLowerCase().includes(busca.toLowerCase()))) &&
        (!tipoPessoa || (p && p.tipo === tipoPessoa)) &&
        (!tipoEvento || l.tipo === tipoEvento)
      );
    })
    .slice()
    .reverse();

  return (
    <div>
      {/* cabeçalho */}
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display m-0 mb-1 text-[23px] font-semibold">Monitoramento</h1>
          <p className="m-0 text-sm text-ink-soft">
            <span className="mr-1.5 inline-block h-[7px] w-[7px] rounded-full bg-good animate-pulse-dot" />
            Registro ao vivo de entradas e saídas pelo reconhecimento facial
          </p>
        </div>
      </div>

      {/* filtros */}
      <div className="mb-[18px] flex flex-wrap items-center gap-2.5">
        {/* busca por nome */}
        <div className="relative min-w-[230px] flex-1">
          <Icon
            name="search"
            size={16}
            className="pointer-events-none absolute left-[11px] top-1/2 -translate-y-1/2 text-ink-faint"
          />
          <input
            className={SEARCH_INPUT}
            placeholder="Buscar por nome"
            value={busca}
            onChange={e => setBusca(e.target.value)}
          />
        </div>
        <select className={SELECT} value={tipoPessoa} onChange={e => setTipoPessoa(e.target.value)}>
          <option value="">Alunos e funcionários</option>
          <option value="aluno">Somente alunos</option>
          <option value="funcionario">Somente funcionários</option>
        </select>
        <select className={SELECT} value={tipoEvento} onChange={e => setTipoEvento(e.target.value)}>
          <option value="">Entradas e saídas</option>
          <option value="entrada">Somente entradas</option>
          <option value="saida">Somente saídas</option>
        </select>
      </div>

      {/* tabela */}
      <div className="overflow-x-auto rounded-lg border border-line bg-surface shadow">
        {lista.length ? (
          <table className="w-full border-collapse text-[13.5px]">
            <thead>
              <tr>
                {['Horário', 'Pessoa', 'Tipo', 'Turma/Cargo', 'Evento', 'Status'].map(h => (
                  <th
                    key={h}
                    className="border-b border-line px-3 pb-2.5 pt-3 text-left text-[11.5px] font-semibold text-ink-faint"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {lista.map(l => (
                <MonitoramentoRow key={l.id} log={l} people={people} onNavigate={onNavigate} />
              ))}
            </tbody>
          </table>
        ) : (
          <div className="p-10 text-center text-ink-faint">Nenhum registro para esse filtro.</div>
        )}
      </div>
    </div>
  );
}
