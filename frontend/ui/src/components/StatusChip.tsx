import type { ReactNode } from "react";

interface StatusChipProps {
  dotColor: string;
  pulse?: boolean;
  label: ReactNode;
  tone?: "default" | "danger" | "nominal";
  mono?: boolean;
}

const toneText: Record<NonNullable<StatusChipProps["tone"]>, string> = {
  default: "text-ink/90",
  danger: "text-danger",
  nominal: "text-nominal",
};

export function StatusChip({
  dotColor,
  pulse,
  label,
  tone = "default",
  mono = true,
}: StatusChipProps) {
  return (
    <div className="glass flex items-center gap-2 rounded-md px-3 py-[7px]">
      <span className="relative flex h-2 w-2">
        {pulse && (
          <span
            className="absolute inline-flex h-full w-full rounded-full opacity-70 animate-pulseRing"
            style={{ backgroundColor: dotColor }}
          />
        )}
        <span
          className="relative inline-flex h-2 w-2 rounded-full"
          style={{ backgroundColor: dotColor, boxShadow: `0 0 8px ${dotColor}` }}
        />
      </span>
      <span
        className={`${mono ? "num" : ""} text-[11px] tracking-[0.14em] ${toneText[tone]}`}
      >
        {label}
      </span>
    </div>
  );
}
