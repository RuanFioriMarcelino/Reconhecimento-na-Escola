import { useState } from 'react';
import Icon from '../../icons/Icon.jsx';
import Button from '../../components/ui/Button.jsx';
import { Field, Input } from '../../components/ui/Field.jsx';

export default function Login({ onLogin }) {
  const [email, setEmail] = useState('coordenacao@escola.edu.br');
  const [senha, setSenha] = useState('protótipo');

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg p-5">
      <div className="w-full max-w-[380px] rounded-xl border border-line bg-surface px-[30px] py-[34px] shadow-card">
        <div className="mb-[18px] flex size-11 items-center justify-center rounded-[10px] bg-primary text-white">
          <Icon name="scan" size={24} />
        </div>
        <h1 className="mb-1.5 text-[19px] font-bold">Painel da coordenação</h1>
        <p className="mb-6 text-[13.5px] text-ink-soft">
          Acesse para acompanhar o cadastro facial e a frequência da escola.
        </p>
        <form onSubmit={(e) => { e.preventDefault(); onLogin(email, senha); }}>
          <Field label="E-mail institucional" className="mb-3">
            <Input type="email" value={email} onChange={e => setEmail(e.target.value)} required />
          </Field>
          <Field label="Senha" className="mb-5">
            <Input type="password" value={senha} onChange={e => setSenha(e.target.value)} required />
          </Field>
          <Button type="submit" block>
            <Icon name="check" size={16} /> Entrar
          </Button>
        </form>
        <p className="mt-4 text-center text-xs text-ink-faint">
          Protótipo de demonstração — qualquer e-mail e senha entram.
        </p>
      </div>
    </div>
  );
}
