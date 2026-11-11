import { useId } from 'react';

interface LogoMarkProps {
  className?: string;
}

/**
 * Texas CRM logo mark: a minimal city skyline on the brand gradient.
 * Pass sizing/shadow classes through `className` (default: 36px).
 */
export function LogoMark({ className = 'w-9 h-9 rounded-[25%]' }: LogoMarkProps) {
  const gradientId = `logo-gradient-${useId().replace(/:/g, '')}`;

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
        <linearGradient id={gradientId} x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
          <stop stopColor="#6366f1" />
          <stop offset="1" stopColor="#4338ca" />
        </linearGradient>
      </defs>
      <rect width="48" height="48" rx="12" fill={`url(#${gradientId})`} />
      <rect x="7.5" y="25" width="6" height="12" rx="1.5" fill="#ffffff" />
      <rect x="16.5" y="17" width="6" height="20" rx="1.5" fill="#ffffff" />
      <rect x="25.5" y="10" width="6" height="27" rx="1.5" fill="#6ee7b7" />
      <rect x="34.5" y="21" width="6" height="16" rx="1.5" fill="#ffffff" />
      <rect x="7.5" y="39.5" width="33" height="1.5" rx="0.75" fill="#ffffff" fillOpacity="0.55" />
    </svg>
  );
}
