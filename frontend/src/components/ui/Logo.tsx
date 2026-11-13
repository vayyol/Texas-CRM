
import { useId } from 'react';

interface LogoMarkProps {
  className?: string;
}

/**
 * TexasCRM logo mark.
 * Geometric white and blue symbol on a black rounded square.
 */
export function LogoMark({
  className = 'w-9 h-9 rounded-[25%]',
}: LogoMarkProps) {
  const clipId = `logo-clip-${useId().replace(/:/g, '')}`;

  return (
    <svg
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label="TexasCRM"
    >
      <defs>
        <clipPath id={clipId}>
          <rect width="48" height="48" rx="7" />
        </clipPath>
      </defs>

      <g clipPath={`url(#${clipId})`}>
        {/* Fundo preto */}
        <rect width="48" height="48" fill="#000000" />

        {/* Barra superior branca */}
        <path
          d="M10 9.2H33.5C37.4 9.2 40 11.9 40 15.2V15.8H10V9.2Z"
          fill="#FFFFFF"
        />

        {/* Bloco vertical branco central */}
        <rect
          x="21.5"
          y="17"
          width="7"
          height="9.5"
          fill="#FFFFFF"
        />

        {/* Estrutura inferior azul */}
        <path
          d="M10 17H17V29H33.5C37.4 29 40 31.7 40 35V36.2H10V17Z"
          fill="#3068F5"
        />
      </g>
    </svg>
  );
}
