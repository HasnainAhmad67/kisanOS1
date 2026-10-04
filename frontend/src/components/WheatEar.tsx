type WheatEarProps = {
  className?: string;
};

/**
 * Decorative wheat-ear SVG (aria-hidden) used as a floating accent on the
 * cinematic hero and other themed surfaces. Motion is CSS-only and is
 * disabled by prefers-reduced-motion in base.css.
 */
export function WheatEar({ className }: WheatEarProps) {
  return (
    <svg
      className={className ? `wheat-ear ${className}` : "wheat-ear"}
      viewBox="0 0 44 128"
      aria-hidden="true"
      focusable="false"
    >
      <g className="wheat-ear__sway">
        {/* stalk */}
        <path
          d="M22 126 C22 96 20 78 22 58"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.4"
          strokeLinecap="round"
          opacity="0.85"
        />
        {/* grains — two staggered columns */}
        <g fill="currentColor">
          <ellipse cx="16" cy="62" rx="6" ry="10.5" transform="rotate(-24 16 62)" />
          <ellipse cx="28" cy="58" rx="6" ry="10.5" transform="rotate(24 28 58)" />
          <ellipse cx="15" cy="48" rx="6" ry="10.5" transform="rotate(-24 15 48)" />
          <ellipse cx="29" cy="44" rx="6" ry="10.5" transform="rotate(24 29 44)" />
          <ellipse cx="16" cy="34" rx="5.6" ry="10" transform="rotate(-24 16 34)" />
          <ellipse cx="28" cy="30" rx="5.6" ry="10" transform="rotate(24 28 30)" />
          <ellipse cx="18" cy="21" rx="5.2" ry="9.5" transform="rotate(-22 18 21)" />
          <ellipse cx="26" cy="18" rx="5.2" ry="9.5" transform="rotate(22 26 18)" />
          <ellipse cx="22" cy="9" rx="4.8" ry="9" />
        </g>
        {/* awns */}
        <g
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
          opacity="0.7"
        >
          <path d="M12 54 L2 34" />
          <path d="M32 50 L42 30" />
          <path d="M13 40 L4 20" />
          <path d="M31 36 L40 16" />
          <path d="M18 14 L13 2" />
          <path d="M26 12 L31 2" />
        </g>
      </g>
    </svg>
  );
}
