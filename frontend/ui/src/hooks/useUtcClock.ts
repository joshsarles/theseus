import { useEffect, useState } from "react";

/** Ticking UTC clock string, HH:MM:SS, updated each second. */
export function useUtcClock(): string {
  const [t, setT] = useState(() => new Date().toISOString().slice(11, 19));
  useEffect(() => {
    const id = setInterval(
      () => setT(new Date().toISOString().slice(11, 19)),
      1000,
    );
    return () => clearInterval(id);
  }, []);
  return t;
}
