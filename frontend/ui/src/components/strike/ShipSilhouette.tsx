interface ShipSilhouetteProps {
  /** color of the worst active severity, drives the hull accent stripe */
  accent: string;
  width?: number;
  height?: number;
}

/**
 * A flat, plan-view destroyer silhouette — hairline vector, no glow. Used on the
 * sister-hull cards so the strike group reads as ships without paying for three
 * full 3D twins. The flagship hero gets the real procedural Warship twin instead.
 */
export function ShipSilhouette({ accent, width = 180, height = 40 }: ShipSilhouetteProps) {
  return (
    <svg width={width} height={height} viewBox="0 0 180 40" fill="none" aria-hidden>
      {/* hull plan view: pointed bow at right, square transom at left */}
      <path
        d="M6 14 L150 14 L174 20 L150 26 L6 26 Z"
        fill="#0d1117"
        stroke="#3a4049"
        strokeWidth={1}
      />
      {/* accent boot stripe along the waterline */}
      <path d="M6 26 L150 26 L160 23" stroke={accent} strokeWidth={1.4} fill="none" />
      {/* superstructure blocks */}
      <rect x={52} y={9} width={20} height={9} fill="#41474f" stroke="#586069" strokeWidth={0.6} />
      <rect x={78} y={11} width={12} height={6} fill="#586069" />
      <rect x={98} y={10} width={16} height={8} fill="#41474f" stroke="#586069" strokeWidth={0.6} />
      {/* mast */}
      <line x1={62} y1={9} x2={62} y2={2} stroke="#6b727b" strokeWidth={1} />
      {/* flight deck hash (stern) */}
      <line x1={14} y1={20} x2={30} y2={20} stroke="#646b75" strokeWidth={0.8} strokeDasharray="2 2" />
      {/* fore gun mount */}
      <rect x={128} y={16} width={8} height={4} fill="#586069" />
    </svg>
  );
}
