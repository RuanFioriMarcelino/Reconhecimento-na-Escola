import { describe, it, expect } from 'vitest';
import { avatarColor, fmtMin, initials } from '../data/seed.js';

describe('Utilitários de formatação e avatar (seed.js)', () => {
  it('calcula iniciais com segurança mesmo em entradas vazias ou nulas', () => {
    expect(initials('Ana Beatriz Silva')).toBe('AS');
    expect(initials('Marina')).toBe('MA');
    expect(initials('')).toBe('?');
    expect(initials('   ')).toBe('?');
    expect(initials(null)).toBe('?');
    expect(initials(undefined)).toBe('?');
  });

  it('gera cor HSL determinística sem lançar exceções em valores nulos', () => {
    expect(avatarColor('Ana Beatriz')).toBe(avatarColor('Ana Beatriz'));
    expect(avatarColor('')).toMatch(/^hsl\(/);
    expect(avatarColor(null)).toMatch(/^hsl\(/);
  });

  it('formata minutos em HH:MM e trata valores inválidos com fallback seguro', () => {
    expect(fmtMin(435)).toBe('07:15');
    expect(fmtMin(0)).toBe('00:00');
    expect(fmtMin(NaN)).toBe('--:--');
    expect(fmtMin(-10)).toBe('--:--');
    expect(fmtMin(undefined)).toBe('--:--');
  });
});
