import PeopleList from '../pessoas/PeopleList.jsx';

export default function AlunosPage({ people, onNavigate }) {
  return <PeopleList tipo="aluno" people={people} onNavigate={onNavigate} />;
}
