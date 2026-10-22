// junta nomes de classe ignorando valores vazios: cx('a', cond && 'b') -> 'a b'
export const cx = (...partes) => partes.filter(Boolean).join(' ');
