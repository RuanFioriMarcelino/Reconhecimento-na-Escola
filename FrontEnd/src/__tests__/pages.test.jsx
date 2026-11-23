import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Login from '../pages/login/Login.jsx';
import Dashboard from '../pages/dashboard/Dashboard.jsx';
import PeopleList from '../pages/pessoas/PeopleList.jsx';
import CadastroFacial from '../pages/cadastro/CadastroFacial.jsx';
import Alertas from '../pages/alertas/Alertas.jsx';
import Configuracoes from '../pages/configuracoes/Configuracoes.jsx';
import { api } from '../lib/api.js';

vi.mock('../lib/api.js', () => ({
  api: {
    dashboard: vi.fn(),
    listPeople: vi.fn(),
    listLogs: vi.fn(),
    listAlerts: vi.fn(),
    updateAlert: vi.fn(),
    getAuditLogs: vi.fn(),
    createDevice: vi.fn(),
    updateDevice: vi.fn(),
  },
}));

describe('Páginas e fluxos críticos do painel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('Login exibe mensagem de erro quando credenciais são rejeitadas', async () => {
    const onLogin = vi.fn().mockRejectedValueOnce(new Error('Credenciais inválidas.'));
    render(<Login onLogin={onLogin} />);

    fireEvent.change(screen.getByPlaceholderText('nome@escola.edu.br'), { target: { value: 'coord@escola.edu.br' } });
    fireEvent.change(screen.getByPlaceholderText('••••••••'), { target: { value: 'errada' } });
    fireEvent.click(screen.getByRole('button', { name: /Entrar no painel/i }));

    await waitFor(() => {
      expect(screen.getByText('Credenciais inválidas.')).toBeInTheDocument();
    });
  });

  it('Dashboard renderiza KPIs e exibe banner de erro com botão Tentar novamente se API falhar', async () => {
    api.dashboard.mockRejectedValueOnce(new Error('Servidor indisponível'));
    render(<Dashboard user={{ nome: 'Marina Silva' }} liveTick={0} onNavigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Servidor indisponível');
    });

    api.dashboard.mockResolvedValueOnce({
      summary: {
        alunosAtivos: 12,
        funcionariosAtivos: 6,
        naEscolaAlunos: 10,
        ausentesHojeAlunos: 2,
        atrasosHojeAlunos: 1,
        presentesHojeFuncionarios: 6,
        atrasosHojeFuncionarios: 0,
        alertasAtivos: 3,
      },
      turmaStats: [{ turma: '6º A', alunosAtivos: 6, presentesHoje: 5, ausentesHoje: 1, pct: 83 }],
      recentes: [],
      abertos: [],
      dispositivos: [{ id: 1, nome: 'Cam 1', online: true }],
    });

    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));

    await waitFor(() => {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
      expect(screen.getByText('6º A')).toBeInTheDocument();
      expect(screen.getByText(/1\/1 câmeras de portaria online/i)).toBeInTheDocument();
    });
  });

  it('PeopleList pagina registros e aplica filtro biométrico', async () => {
    api.listPeople.mockResolvedValue({
      items: [
        { id: 'aluno-1', nome: 'Ana Clara', grupo: '6º A', documento: '20260001', status: 'ativo', biometriaCadastrada: true, biometriaQualidade: 0.95 },
      ],
      pagination: { page: 1, pageSize: 24, total: 1, totalPages: 1, hasPrev: false, hasNext: false },
    });

    render(<PeopleList tipo="aluno" turmas={[{ id: 1, nome: '6º A' }]} liveTick={0} onNavigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Ana Clara')).toBeInTheDocument();
    });

    const selects = screen.getAllByRole('combobox');
    fireEvent.change(selects[1], { target: { value: 'sim' } });

    await waitFor(() => {
      expect(api.listPeople).toHaveBeenLastCalledWith(expect.objectContaining({ tipo: 'aluno', biometria: 'sim', page: 1 }));
    });
  });

  it('CadastroFacial exige consentimento LGPD ao enviar foto e preserva savedPersonId em erro biométrico', async () => {
    const showToast = vi.fn();
    const onNavigate = vi.fn();
    const bioErr = new Error('Nenhum rosto detectado na imagem.');
    bioErr.savedPersonId = 'aluno-99';
    const onSubmitPerson = vi.fn().mockRejectedValueOnce(bioErr).mockResolvedValueOnce('aluno-99');

    const origCreate = URL.createObjectURL;
    const origRevoke = URL.revokeObjectURL;
    URL.createObjectURL = vi.fn(() => 'blob:face');
    URL.revokeObjectURL = vi.fn();

    render(
      <CadastroFacial
        tipoInicial="aluno"
        turmas={[{ id: 1, nome: '6º A', turno: 'Manhã' }]}
        onSubmitPerson={onSubmitPerson}
        onNavigate={onNavigate}
        showToast={showToast}
      />
    );

    fireEvent.change(screen.getByPlaceholderText('Ex.: Maria Eduarda Souza'), { target: { value: 'Pedro Henrique' } });
    fireEvent.change(screen.getByPlaceholderText('2026XXXX'), { target: { value: '20269999' } });
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '1' } });
    fireEvent.change(screen.getByPlaceholderText('Nome completo'), { target: { value: 'Carlos Henrique' } });
    fireEvent.change(screen.getByPlaceholderText('(00) 90000-0000'), { target: { value: '(48) 99999-0000' } });

    const fileInput = document.querySelector('input[type="file"]');
    fireEvent.change(fileInput, { target: { files: [new File(['x'], 'foto.jpg', { type: 'image/jpeg' })] } });

    // Sem marcar consentimento LGPD -> bloqueia envio
    fireEvent.click(screen.getByRole('button', { name: /Concluir cadastro/i }));
    expect(showToast).toHaveBeenCalledWith(expect.stringContaining('consentimento biométrico'), 'triangle');
    expect(onSubmitPerson).not.toHaveBeenCalled();

    // Marca LGPD e envia -> 1a tentativa falha na biometria mas preserva savedPersonId
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: /Concluir cadastro/i }));

    await waitFor(() => {
      expect(screen.getByText(/Pessoa já salva no banco/i)).toBeInTheDocument();
    });

    // Reenvio usa savedPersonId='aluno-99' sem duplicar pessoa
    fireEvent.click(screen.getByRole('button', { name: /Concluir cadastro/i }));
    await waitFor(() => {
      expect(onSubmitPerson).toHaveBeenLastCalledWith(expect.any(Object), expect.any(Array), 'aluno-99');
      expect(onNavigate).toHaveBeenCalledWith('pessoa', 'aluno', 'aluno-99');
    });

    URL.createObjectURL = origCreate;
    URL.revokeObjectURL = origRevoke;
  });

  it('Alertas lista avisos e marca alerta como resolvido', async () => {
    api.listAlerts.mockResolvedValue({
      items: [
        { id: 7, tipo: 'Atraso na entrada', descricao: 'Entrada às 07:40', severidade: 'media', status: 'novo', personName: 'Ana Teste' },
      ],
      openCount: 1,
      pagination: { page: 1, pageSize: 20, total: 1, totalPages: 1, hasPrev: false, hasNext: false },
    });
    api.updateAlert.mockResolvedValueOnce({ id: 7, status: 'resolvido' });
    const showToast = vi.fn();

    render(<Alertas liveTick={0} onAlertChanged={vi.fn()} showToast={showToast} />);

    await waitFor(() => {
      expect(screen.getByText('Atraso na entrada')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Resolver/i }));
    await waitFor(() => {
      expect(api.updateAlert).toHaveBeenCalledWith(7, { status: 'resolvido' });
      expect(showToast).toHaveBeenCalledWith('Alerta marcado como resolvido', 'check');
    });
  });

  it('Configuracoes aplica modo somente leitura para secretaria e habilita edição para coordenacao', async () => {
    const baseSettings = {
      nomeEscola: 'Escola Teste',
      limiteManha: '07:20',
      limiteTarde: '13:20',
      saidaManha: '11:30',
      saidaTarde: '17:30',
      cooldownSegundos: 45,
      tempoMinimoPermanenciaMin: 2,
      limiarConfianca: 0.38,
      retencaoLogsDias: 365,
      modoPassivo: true,
      notifAtraso: true,
      notifAusencia: true,
      notifNaoReconhecido: true,
      notifSaidaAntecipada: true,
    };

    const { rerender } = render(
      <Configuracoes
        user={{ nome: 'Carla Sec', papel: 'secretaria' }}
        settings={baseSettings}
        onSaveSettings={vi.fn()}
        turmas={[]}
        turnos={[]}
        dispositivos={[]}
        onAddClass={vi.fn()}
        onRefresh={vi.fn()}
        showToast={vi.fn()}
      />
    );

    expect(screen.getByRole('status')).toHaveTextContent(/Modo somente leitura/i);
    expect(screen.queryByRole('button', { name: /Salvar configurações/i })).not.toBeInTheDocument();

    api.getAuditLogs.mockResolvedValueOnce({ items: [], pagination: { page: 1, pageSize: 20, total: 0, totalPages: 1 } });
    rerender(
      <Configuracoes
        user={{ nome: 'Marina Coord', papel: 'coordenacao' }}
        settings={baseSettings}
        onSaveSettings={vi.fn()}
        turmas={[]}
        turnos={[]}
        dispositivos={[]}
        onAddClass={vi.fn()}
        onRefresh={vi.fn()}
        showToast={vi.fn()}
      />
    );

    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Salvar configurações/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(api.getAuditLogs).toHaveBeenCalledTimes(1);
    });
  });
});
