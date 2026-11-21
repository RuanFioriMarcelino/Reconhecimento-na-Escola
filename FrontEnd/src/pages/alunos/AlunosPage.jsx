import PeopleList from '../pessoas/PeopleList.jsx';

export default function AlunosPage({ turmas, liveTick, onNavigate }) {
  return <PeopleList tipo="aluno" turmas={turmas} liveTick={liveTick} onNavigate={onNavigate} />;
}
