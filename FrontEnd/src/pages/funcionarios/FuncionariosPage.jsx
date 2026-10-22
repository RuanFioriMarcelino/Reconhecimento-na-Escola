import PeopleList from '../pessoas/PeopleList.jsx';

export default function FuncionariosPage({ people, onNavigate }) {
  return <PeopleList tipo="funcionario" people={people} onNavigate={onNavigate} />;
}
