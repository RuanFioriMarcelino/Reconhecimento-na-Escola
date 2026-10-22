/* =====================================================================
   HELPERS GERAIS
===================================================================== */
export function mulberry32(seed) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
export const baseRng = mulberry32(1337);
export function pick(arr) { return arr[Math.floor(baseRng() * arr.length)]; }
export function pad(n) { return n < 10 ? '0' + n : '' + n; }
export function fmtMin(mins) {
  const h = Math.floor(mins / 60), m = mins % 60;
  return pad(h) + ':' + pad(m);
}
function hashStr(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) >>> 0; }
  return h;
}
const AVATAR_HUES = [210, 20, 160, 280, 35, 190, 340, 90, 255, 10];
export function avatarColor(name) {
  return 'hsl(' + AVATAR_HUES[hashStr(name) % AVATAR_HUES.length] + ', 38%, 40%)';
}
export function initials(name) {
  const p = name.trim().split(/\s+/);
  return (p[0][0] + (p[p.length - 1][0] || '')).toUpperCase();
}

/* =====================================================================
   CONSTANTES
===================================================================== */
export const NOMES_ALUNOS = [
  "Ana Beatriz Silva", "Bruno Costa Lima", "Carla Eduarda Santos", "Davi Henrique Oliveira",
  "Elisa Fernandes Rocha", "Felipe Augusto Souza", "Gabriela Martins Alves", "Heitor Ribeiro Dias",
  "Isabela Cristina Pereira", "João Pedro Nascimento", "Larissa Gomes Teixeira", "Matheus Vinícius Barbosa",
  "Nicole Almeida Cardoso", "Otávio Ramos Freitas", "Paula Regina Moura", "Rafael Augusto Pinto",
  "Sofia Helena Correia", "Thiago Matheus Araújo", "Valentina Duarte Nunes", "Wesley Rodrigues Farias",
  "Yasmin Carvalho Batista", "Vitor Hugo Monteiro"
];
export const NOMES_FUNCIONARIOS = [
  "Camila Ferreira Rocha", "Eduardo Santos Lima", "Beatriz Nogueira Alves", "Marcelo Andrade Souza",
  "Renata Vieira Costa", "Fábio Henrique Moreira", "Juliana Prado Martins", "André Luiz Barros",
  "Patrícia Nunes Cardoso", "Cláudio Ramos Teixeira"
];
export const TURMAS = ["6º A", "6º B", "7º A", "7º B", "9º A"];
export const CARGOS = [
  "Professor(a) — Matemática", "Professor(a) — Português", "Professor(a) — Ciências",
  "Professor(a) — Educação Física", "Coordenador(a) Pedagógico(a)", "Secretário(a) Escolar",
  "Auxiliar de Serviços Gerais", "Porteiro(a)", "Diretor(a)", "Professor(a) — Artes"
];

export function turnoDaTurma(t) { return t.startsWith('9') ? 'Tarde' : 'Manhã'; }
export function janelaDoTurno(turno) {
  if (turno === 'Tarde') return [13 * 60, 13 * 60 + 35];
  return [7 * 60, 7 * 60 + 35]; // Manhã e Integral usam a mesma janela de entrada
}
export function limiteDoTurno(turno) {
  return turno === 'Tarde' ? 13 * 60 + 20 : 7 * 60 + 20;
}

export const PERSON_CONFIG = {
  aluno: {
    singular: 'Aluno', plural: 'Alunos', icon: 'users',
    grupoLabel: 'Turma', grupoOptions: TURMAS,
    documentoLabel: 'Matrícula', documentoPlaceholder: '2026XXXX',
    contatoNomeLabel: 'Responsável', contatoTelefoneLabel: 'Contato do responsável',
    dataLabel: 'Nascimento'
  },
  funcionario: {
    singular: 'Funcionário(a)', plural: 'Funcionários', icon: 'briefcase',
    grupoLabel: 'Cargo', grupoOptions: CARGOS,
    documentoLabel: 'Matrícula funcional', documentoPlaceholder: 'FUNC-0000',
    contatoNomeLabel: 'Contato de emergência', contatoTelefoneLabel: 'Telefone de emergência',
    dataLabel: 'Admissão'
  }
};

/* =====================================================================
   GERAÇÃO DE DADOS DE EXEMPLO
===================================================================== */
export function seedPeople() {
  let id = 1;
  const alunos = NOMES_ALUNOS.map((nome, i) => {
    const turma = TURMAS[i % TURMAS.length];
    return {
      id: id++, tipo: 'aluno', nome,
      documento: '2026' + String(1000 + i),
      grupo: turma, turno: turnoDaTurma(turma),
      status: (i === 13) ? 'inativo' : 'ativo',
      contatoNome: 'Responsável de ' + nome.split(' ')[0],
      contatoTelefone: '(48) 9' + ((8000 + i * 173) % 9000) + '-' + ((1000 + i * 97) % 9000),
      dataCadastro: '12/02/2026',
      dataRef: pad(3 + (i % 25)) + '/0' + (2 + (i % 9) % 9) + '/' + (2012 + (i % 4))
    };
  });
  const funcionarios = NOMES_FUNCIONARIOS.map((nome, i) => {
    const cargo = CARGOS[i % CARGOS.length];
    const turno = i % 3 === 0 ? 'Integral' : (i % 2 === 0 ? 'Manhã' : 'Tarde');
    return {
      id: id++, tipo: 'funcionario', nome,
      documento: 'FUNC-' + String(300 + i),
      grupo: cargo, turno,
      status: 'ativo',
      contatoNome: 'Contato de emergência de ' + nome.split(' ')[0],
      contatoTelefone: '(48) 9' + ((7000 + i * 211) % 9000) + '-' + ((2000 + i * 61) % 9000),
      dataCadastro: '20/01/2026',
      dataRef: '0' + (1 + (i % 9)) + '/0' + (1 + (i % 9)) + '/' + (2018 + (i % 6))
    };
  });
  return [...alunos, ...funcionarios];
}

export function seedLogsAndAlerts(people) {
  let logId = 1, alertId = 1;
  const logs = [];
  people.forEach((p, i) => {
    if (p.status === 'inativo') return;
    const ausente = (i % 7 === 4);
    if (ausente) return;
    const [ini, fim] = janelaDoTurno(p.turno);
    const minuto = ini + Math.floor(baseRng() * (fim - ini));
    const atrasado = minuto > limiteDoTurno(p.turno);
    logs.push({
      id: logId++, personId: p.id, tipo: 'entrada', horaMin: minuto,
      status: atrasado ? 'atraso' : 'reconhecido', local: 'Portaria principal'
    });
    if (i % 9 === 0) {
      logs.push({
        id: logId++, personId: p.id, tipo: 'saida', horaMin: minuto + 180,
        status: 'reconhecido', local: 'Portaria principal'
      });
    }
  });
  logs.push({ id: logId++, personId: null, tipo: 'entrada', horaMin: 7 * 60 + 12, status: 'nao-reconhecido', local: 'Catraca lateral' });
  logs.push({ id: logId++, personId: null, tipo: 'entrada', horaMin: 13 * 60 + 8, status: 'nao-reconhecido', local: 'Portaria principal' });
  logs.sort((a, b) => a.horaMin - b.horaMin);

  const alerts = [];
  logs.forEach(l => {
    if (l.status === 'atraso') {
      alerts.push({
        id: alertId++, personId: l.personId, tipo: 'Atraso na entrada',
        descricao: 'Entrada registrada às ' + fmtMin(l.horaMin) + ', após o horário limite.',
        severidade: 'media', status: (alertId % 5 === 0) ? 'resolvido' : 'novo'
      });
    }
    if (l.status === 'nao-reconhecido') {
      alerts.push({
        id: alertId++, personId: null, tipo: 'Tentativa não reconhecida',
        descricao: 'Reconhecimento facial não identificou nenhum cadastro.',
        severidade: 'alta', status: 'novo'
      });
    }
  });
  const presentesIds = new Set(logs.filter(l => l.tipo === 'entrada' && l.personId).map(l => l.personId));
  people.forEach(p => {
    if (p.status === 'ativo' && !presentesIds.has(p.id)) {
      alerts.push({
        id: alertId++, personId: p.id, tipo: 'Ausência não justificada',
        descricao: 'Nenhum registro de entrada até o momento.', severidade: 'alta', status: 'novo'
      });
    }
  });
  const alunoRecorrente = people.find(p => p.tipo === 'aluno');
  alerts.push({
    id: alertId++, personId: alunoRecorrente.id, tipo: 'Ausência recorrente',
    descricao: '3ª ausência sem justificativa nos últimos 10 dias letivos.', severidade: 'alta', status: 'em-analise'
  });
  const funcRecorrente = people.find(p => p.tipo === 'funcionario');
  alerts.push({
    id: alertId++, personId: funcRecorrente.id, tipo: 'Atraso recorrente',
    descricao: '2º atraso na entrada nesta semana.', severidade: 'media', status: 'novo'
  });

  alerts.sort((a, b) => {
    const order = { novo: 0, 'em-analise': 1, resolvido: 2 };
    return order[a.status] - order[b.status];
  });
  return { logs, alerts, nextLogId: logId, nextAlertId: alertId };
}

export function historicoPessoa(personId) {
  const dias = ['Seg 08/09', 'Ter 09/09', 'Qua 10/09', 'Qui 11/09', 'Sex 12/09'];
  const r = mulberry32(personId * 97 + 3);
  return dias.map(d => {
    const roll = r();
    let status = 'presente', hora = '07:0' + Math.floor(r() * 9);
    if (roll < 0.12) { status = 'falta'; hora = '—'; }
    else if (roll < 0.26) { status = 'atraso'; hora = '07:3' + Math.floor(r() * 9); }
    return { dia: d, status, hora };
  });
}
