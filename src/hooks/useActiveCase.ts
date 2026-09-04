import { useCallback, useEffect, useState } from "react";
import { api, type CaseRecord } from "../ipc";

export function useActiveCase(): {
  active: CaseRecord | null;
  refresh: () => Promise<void>;
} {
  const [active, setActive] = useState<CaseRecord | null>(null);
  const refresh = useCallback(async () => {
    try {
      const c = await api.activeCase();
      setActive(c);
    } catch (e) {
      console.error("activeCase failed", e);
      setActive(null);
    }
  }, []);
  useEffect(() => {
    refresh();
  }, [refresh]);
  return { active, refresh };
}