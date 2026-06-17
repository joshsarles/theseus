interface SectionHeadProps {
  index?: string;
  title: string;
  meta?: string;
}

/**
 * A precise section header: monospace index tag · display title · right-aligned
 * mono meta. Sharp, orthogonal, hairline-divided.
 */
export function SectionHead({ index, title, meta }: SectionHeadProps) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "baseline",
        gap: 10,
        padding: "10px 14px",
        borderBottom: "1px solid var(--hair)",
      }}
    >
      {index ? (
        <span
          className="mono"
          style={{ fontSize: 10, color: "var(--muted)", letterSpacing: "0.1em" }}
        >
          {index}
        </span>
      ) : null}
      <span
        className="display"
        style={{
          fontSize: 12.5,
          fontWeight: 600,
          letterSpacing: "0.04em",
          textTransform: "uppercase",
          color: "var(--ink)",
        }}
      >
        {title}
      </span>
      {meta ? (
        <span
          className="mono"
          style={{
            marginLeft: "auto",
            fontSize: 10.5,
            color: "var(--muted)",
            letterSpacing: "0.02em",
          }}
        >
          {meta}
        </span>
      ) : null}
    </div>
  );
}
