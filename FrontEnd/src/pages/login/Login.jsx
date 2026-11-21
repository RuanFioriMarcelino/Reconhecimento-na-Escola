import { useState } from 'react';
import Icon from '../../icons/Icon.jsx';
import Button from '../../components/ui/Button.jsx';
import { Field, Input } from '../../components/ui/Field.jsx';

export default function Login({ onLogin }) {
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    setErrorMsg('');
    setLoading(true);
    try {
      await onLogin(email.trim(), senha);
    } catch (error) {
      setErrorMsg(error.message || 'Falha ao autenticar.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg p-5">
      <div className="w-full max-w-[400px] rounded-xl border border-line bg-surface px-[30px] py-[34px] shadow-card">
        <div className="mb-[18px] flex size-11 items-center justify-center rounded-[10px] bg-primary text-white">
          <Icon name="scan" size={24} />
        </div>
        <h1 className="mb-1.5 text-[19px] font-bold">Reconhece+ v2.0</h1>
        <p className="mb-6 text-[13.5px] text-ink-soft">
          Painel administrativo e coordenação — monitoramento biométrico escolar.
        </p>

        {errorMsg && (
          <div className="mb-4 rounded-lg border border-danger bg-danger-soft px-3 py-2 text-xs font-medium text-danger">
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <Field label="E-mail institucional" className="mb-3">
            <Input
              type="email"
              placeholder="nome@escola.edu.br"
              value={email}
              onChange={e => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </Field>
          <Field label="Senha" className="mb-5">
            <Input
              type="password"
              placeholder="••••••••"
              value={senha}
              onChange={e => setSenha(e.target.value)}
              autoComplete="current-password"
              required
            />
          </Field>
          <Button type="submit" block disabled={loading}>
            <Icon name="check" size={16} /> {loading ? 'Autenticando...' : 'Entrar no painel'}
          </Button>
        </form>
        <p className="mt-4 text-center text-xs text-ink-faint">
          Acesso restrito a usuários autorizados · Conformidade LGPD
        </p>
      </div>
    </div>
  );
}
