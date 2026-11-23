import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import PaginationBar from '../components/PaginationBar.jsx';
import { AlertStatusPill, BiometriaPill, LogStatusPill, TipoPill } from '../components/Pills.jsx';
import ErrorBoundary from '../components/ErrorBoundary.jsx';
import CameraCaptura from '../components/CameraCaptura.jsx';

describe('Componentes reutilizáveis', () => {
  it('PaginationBar exibe intervalo, desabilita botões nos limites e aciona callbacks', () => {
    const onPageChange = vi.fn();
    const onPageSizeChange = vi.fn();

    render(
      <PaginationBar
        pagination={{ page: 2, pageSize: 25, total: 60, totalPages: 3, hasPrev: true, hasNext: true }}
        onPageChange={onPageChange}
        onPageSizeChange={onPageSizeChange}
      />
    );

    expect(screen.getByText(/26–50/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Anterior' }));
    expect(onPageChange).toHaveBeenCalledWith(1);
    fireEvent.click(screen.getByRole('button', { name: 'Próxima' }));
    expect(onPageChange).toHaveBeenCalledWith(3);

    fireEvent.change(screen.getByLabelText('Itens por página'), { target: { value: '50' } });
    expect(onPageSizeChange).toHaveBeenCalledWith(50);
  });

  it('Pills renderizam todos os estados corretamente', () => {
    render(
      <div>
        <LogStatusPill status="atraso" />
        <LogStatusPill status="saida-antecipada" />
        <LogStatusPill status="nao-reconhecido" />
        <LogStatusPill status="reconhecido" />
        <AlertStatusPill status="novo" />
        <AlertStatusPill status="em-analise" />
        <AlertStatusPill status="resolvido" />
        <TipoPill tipo="aluno" />
        <TipoPill tipo="funcionario" />
        <BiometriaPill cadastrada={true} qualidade={0.93} />
        <BiometriaPill cadastrada={false} />
      </div>
    );

    expect(screen.getByText('Atraso')).toBeInTheDocument();
    expect(screen.getByText('Saída antecipada')).toBeInTheDocument();
    expect(screen.getByText('Não reconhecido')).toBeInTheDocument();
    expect(screen.getByText('Reconhecido')).toBeInTheDocument();
    expect(screen.getByText('Novo')).toBeInTheDocument();
    expect(screen.getByText('Em análise')).toBeInTheDocument();
    expect(screen.getByText('Resolvido')).toBeInTheDocument();
    expect(screen.getByText('Aluno')).toBeInTheDocument();
    expect(screen.getByText('Funcionário')).toBeInTheDocument();
    expect(screen.getByText(/Biometria ativa \(93%\)/)).toBeInTheDocument();
    expect(screen.getByText('Biometria pendente')).toBeInTheDocument();
  });

  it('ErrorBoundary captura exceções de renderização e oferece recuperação', () => {
    const spyError = vi.spyOn(console, 'error').mockImplementation(() => {});
    const onReset = vi.fn();

    function BrokenChild() {
      throw new Error('Falha simulada no componente');
    }

    render(
      <ErrorBoundary onReset={onReset}>
        <BrokenChild />
      </ErrorBoundary>
    );

    expect(screen.getByText('Algo deu errado na interface')).toBeInTheDocument();
    expect(screen.getByText('Falha simulada no componente')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Recarregar painel' }));
    expect(onReset).toHaveBeenCalledTimes(1);
    spyError.mockRestore();
  });

  it('CameraCaptura exibe aviso amigável sem webcam e aceita envio de foto', () => {
    const onCaptured = vi.fn();
    const origCreateObjectURL = URL.createObjectURL;
    const origRevokeObjectURL = URL.revokeObjectURL;
    URL.createObjectURL = vi.fn(() => 'blob:mock-preview');
    URL.revokeObjectURL = vi.fn();

    render(<CameraCaptura onCaptured={onCaptured} />);
    fireEvent.click(screen.getByRole('button', { name: /Abrir câmera de registro/i }));
    expect(screen.getByText(/Navegador sem suporte à webcam/i)).toBeInTheDocument();

    const fileInput = document.querySelector('input[type="file"]');
    const file = new File(['img-bytes'], 'rosto.jpg', { type: 'image/jpeg' });
    fireEvent.change(fileInput, { target: { files: [file] } });
    expect(onCaptured).toHaveBeenCalledWith([file]);

    URL.createObjectURL = origCreateObjectURL;
    URL.revokeObjectURL = origRevokeObjectURL;
  });
});
