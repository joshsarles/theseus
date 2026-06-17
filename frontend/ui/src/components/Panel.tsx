import type { ReactNode } from "react";
import { motion } from "framer-motion";

interface PanelProps {
  title: ReactNode;
  meta?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  delay?: number;
  scroll?: boolean;
}

export function Panel({
  title,
  meta,
  children,
  className = "",
  bodyClassName = "",
  delay = 0,
  scroll = false,
}: PanelProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1], delay }}
      className={`glass flex min-h-0 flex-col rounded-xl ${className}`}
    >
      <div className="flex shrink-0 items-center justify-between gap-3 px-3.5 pt-3 pb-2.5">
        <div className="eyebrow flex items-center gap-2">
          <span className="inline-block h-[10px] w-[2px] rounded bg-cyan box-glow-cyan" />
          {title}
        </div>
        {meta && <div className="num text-[10px] text-cyan/80">{meta}</div>}
      </div>
      <div
        className={`min-h-0 flex-1 px-3.5 pb-3.5 ${scroll ? "overflow-y-auto" : ""} ${bodyClassName}`}
      >
        {children}
      </div>
    </motion.section>
  );
}
