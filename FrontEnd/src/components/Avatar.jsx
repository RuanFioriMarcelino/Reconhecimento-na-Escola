import { avatarColor, initials } from '../data/seed.js';

// cor, tamanho e raio dependem do nome/props em tempo de execução, por isso ficam em style
export default function Avatar({ nome, size = 40, square = false }) {
  const style = {
    width: size, height: size, background: avatarColor(nome),
    fontSize: Math.round(size * 0.38), borderRadius: square ? 8 : '50%',
  };
  return (
    <div
      className="flex shrink-0 items-center justify-center font-display font-semibold text-white"
      style={style}
    >
      {initials(nome)}
    </div>
  );
}
