import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { api, clearToken, getToken, setToken, setUnauthorizedHandler } from '../lib/api.js';

describe('Cliente HTTP (api.js)', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    clearToken();
    setUnauthorizedHandler(null);
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('salva token no login e envia header Bearer nas requisições seguintes', async () => {
    global.fetch = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ token: 'rne_tok_123', user: { nome: 'Marina', papel: 'coordenacao' } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ items: [], pagination: { page: 1, pageSize: 24, total: 0, totalPages: 1 } }),
      });

    await api.login('coord@escola.edu.br', 'Coord@2026');
    expect(getToken()).toBe('rne_tok_123');

    await api.listPeople({ tipo: 'aluno', search: 'Ana', grupo: '', page: 2 });
    const [url, opts] = global.fetch.mock.calls[1];
    expect(url).toContain('/people/?tipo=aluno&search=Ana&page=2');
    expect(url).not.toContain('grupo=');
    expect(opts.headers.Authorization).toBe('Bearer rne_tok_123');
  });

  it('limpa token e chama unauthorizedHandler ao receber HTTP 401 fora do login', async () => {
    setToken('rne_expired');
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);

    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Sessão expirada.' }),
    });

    await expect(api.me()).rejects.toThrow('Sessão expirada.');
    expect(getToken()).toBe('');
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it('envia FormData sem sobrescrever Content-Type em enrollBiometrics', async () => {
    setToken('rne_valid');
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({ biometriaId: 10, qualidade: 0.91 }),
    });

    const file = new File(['fake-jpg'], 'face.jpg', { type: 'image/jpeg' });
    const res = await api.enrollBiometrics('aluno-1', [file]);
    expect(res.biometriaId).toBe(10);

    const [, opts] = global.fetch.mock.calls[0];
    expect(opts.body).toBeInstanceOf(FormData);
    expect(opts.headers['Content-Type']).toBeUndefined();
    expect(opts.headers.Authorization).toBe('Bearer rne_valid');
  });
});
