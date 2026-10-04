/**
 * Layered farm scene — inline SVG only (no external images).
 * Layers: dawn sky gradient + sun (CSS), drifting clouds, distant hills,
 * midground field rows, foreground swaying wheat stalks.
 * Decorative (aria-hidden) — all meaning lives in the page text.
 */
export function FarmScene() {
  return (
    <svg
      className="farm-scene"
      viewBox="0 0 480 240"
      preserveAspectRatio="xMidYMax slice"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient id="fs-hill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#7d8f6a" />
          <stop offset="100%" stopColor="#5d7050" />
        </linearGradient>
        <linearGradient id="fs-field" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#b99a4e" />
          <stop offset="100%" stopColor="#8f7433" />
        </linearGradient>
        <linearGradient id="fs-near" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#a4863c" />
          <stop offset="100%" stopColor="#6f5a26" />
        </linearGradient>
      </defs>

      {/* drifting clouds */}
      <g className="farm-scene__cloud farm-scene__cloud--a">
        <ellipse cx="90" cy="44" rx="34" ry="11" fill="#fff" opacity="0.85" />
        <ellipse cx="116" cy="38" rx="22" ry="9" fill="#fff" opacity="0.75" />
      </g>
      <g className="farm-scene__cloud farm-scene__cloud--b">
        <ellipse cx="330" cy="30" rx="40" ry="12" fill="#fff" opacity="0.7" />
        <ellipse cx="360" cy="24" rx="24" ry="9" fill="#fff" opacity="0.6" />
      </g>

      {/* distant hills */}
      <path
        d="M0 132 Q70 96 150 118 Q230 140 300 108 Q380 78 480 122 L480 160 L0 160 Z"
        fill="url(#fs-hill)"
        opacity="0.9"
      />
      <path
        d="M0 148 Q110 122 220 142 Q330 162 480 138 L480 170 L0 170 Z"
        fill="#4f6344"
        opacity="0.9"
      />

      {/* midground field rows */}
      <path
        d="M0 158 Q240 140 480 158 L480 200 L0 200 Z"
        fill="url(#fs-field)"
      />
      <g stroke="#6f5a26" strokeWidth="2" opacity="0.35">
        <path d="M20 168 Q240 154 460 168" fill="none" />
        <path d="M10 178 Q240 164 470 178" fill="none" />
        <path d="M0 188 Q240 174 480 188" fill="none" />
      </g>

      {/* foreground soil band */}
      <path
        d="M0 196 Q240 184 480 196 L480 240 L0 240 Z"
        fill="url(#fs-near)"
      />

      {/* swaying wheat stalks (staggered) — outer g keeps the position,
          inner g carries the CSS sway animation */}
      <g className="farm-scene__stalks" stroke="#e4c25f" fill="none">
        <g transform="translate(36 236)">
          <g className="stalk stalk--1">
            <path d="M0 0 C -2 -22 2 -40 0 -56" strokeWidth="3" />
            <path d="M0 -46 l -7 -7 M0 -46 l 7 -7 M0 -54 l -6 -7 M0 -54 l 6 -7 M0 -62 l -5 -6 M0 -62 l 5 -6" strokeWidth="2.5" />
          </g>
        </g>
        <g transform="translate(96 240)">
          <g className="stalk stalk--2">
            <path d="M0 0 C 2 -26 -2 -46 0 -64" strokeWidth="3.2" />
            <path d="M0 -52 l -7 -7 M0 -52 l 7 -7 M0 -60 l -6 -7 M0 -60 l 6 -7 M0 -68 l -5 -6 M0 -68 l 5 -6" strokeWidth="2.5" />
          </g>
        </g>
        <g transform="translate(160 238)">
          <g className="stalk stalk--3">
            <path d="M0 0 C -3 -20 1 -36 0 -50" strokeWidth="2.8" />
            <path d="M0 -40 l -6 -6 M0 -40 l 6 -6 M0 -48 l -6 -6 M0 -48 l 6 -6 M0 -56 l -5 -5 M0 -56 l 5 -5" strokeWidth="2.3" />
          </g>
        </g>
        <g transform="translate(240 242)">
          <g className="stalk stalk--4">
            <path d="M0 0 C 3 -28 -1 -48 0 -66" strokeWidth="3.2" />
            <path d="M0 -54 l -7 -7 M0 -54 l 7 -7 M0 -62 l -6 -7 M0 -62 l 6 -7 M0 -70 l -5 -6 M0 -70 l 5 -6" strokeWidth="2.5" />
          </g>
        </g>
        <g transform="translate(312 238)">
          <g className="stalk stalk--5">
            <path d="M0 0 C -2 -24 2 -42 0 -58" strokeWidth="3" />
            <path d="M0 -48 l -7 -7 M0 -48 l 7 -7 M0 -56 l -6 -7 M0 -56 l 6 -7 M0 -64 l -5 -6 M0 -64 l 5 -6" strokeWidth="2.4" />
          </g>
        </g>
        <g transform="translate(384 242)">
          <g className="stalk stalk--6">
            <path d="M0 0 C 2 -26 -2 -46 0 -62" strokeWidth="3.1" />
            <path d="M0 -50 l -7 -7 M0 -50 l 7 -7 M0 -58 l -6 -7 M0 -58 l 6 -7 M0 -66 l -5 -6 M0 -66 l 5 -6" strokeWidth="2.5" />
          </g>
        </g>
        <g transform="translate(448 236)">
          <g className="stalk stalk--7">
            <path d="M0 0 C -3 -22 1 -40 0 -54" strokeWidth="2.9" />
            <path d="M0 -44 l -6 -6 M0 -44 l 6 -6 M0 -52 l -6 -6 M0 -52 l 6 -6 M0 -60 l -5 -5 M0 -60 l 5 -5" strokeWidth="2.3" />
          </g>
        </g>
      </g>
    </svg>
  );
}
