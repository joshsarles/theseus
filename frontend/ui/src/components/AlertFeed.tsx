import { useMemo } from "react";
import { AnimatePresence } from "framer-motion";
import type { Contact } from "../lib/types";
import { CONTACT_ORDER } from "../lib/palette";
import { ContactAlert, type ReviewVerdict } from "./ContactAlert";

interface AlertFeedProps {
  contacts: Contact[];
  reviews: Record<string, ReviewVerdict>;
  onReview: (id: string, verdict: ReviewVerdict) => void;
  limit?: number;
}

export function AlertFeed({
  contacts,
  reviews,
  onReview,
  limit = 40,
}: AlertFeedProps) {
  // Sort by urgency only (position_jump first). Reviewed cards stay in place so
  // the watch officer's verdict badge remains visible where they acted.
  const sorted = useMemo(() => {
    return [...contacts]
      .sort(
        (a, b) =>
          (CONTACT_ORDER[a.type] ?? 9) - (CONTACT_ORDER[b.type] ?? 9),
      )
      .slice(0, limit);
  }, [contacts, limit]);

  return (
    <div className="flex flex-col gap-2">
      <AnimatePresence initial={false} mode="popLayout">
        {sorted.map((c, i) => (
          <ContactAlert
            key={c.id}
            contact={c}
            index={i}
            verdict={reviews[c.id]}
            onReview={onReview}
          />
        ))}
      </AnimatePresence>
    </div>
  );
}
