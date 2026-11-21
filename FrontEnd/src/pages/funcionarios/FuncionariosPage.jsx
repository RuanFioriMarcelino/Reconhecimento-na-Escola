import PeopleList from '../pessoas/PeopleList.jsx';

export default function FuncionariosPage({ liveTick, onNavigate }) {
  return <PeopleList tipo="funcionario" liveTick={liveTick} onNavigate={onNavigate} />;
}
