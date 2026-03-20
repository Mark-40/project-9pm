import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { SignalLogEntry } from "@/lib/types";
import { MAX_SIGNAL_LOG } from "@/lib/constants";
import { generateId } from "@/lib/utils";

interface SignalLogStore {
  entries: SignalLogEntry[];
  add: (entry: Omit<SignalLogEntry, "id">) => void;
  clear: () => void;
}

export const useSignalLogStore = create<SignalLogStore>()(
  persist(
    (set) => ({
      entries: [],
      add: (entry) =>
        set((state) => ({
          entries: [{ ...entry, id: generateId() }, ...state.entries].slice(
            0,
            MAX_SIGNAL_LOG
          ),
        })),
      clear: () => set({ entries: [] }),
    }),
    {
      name: "crypto-signal-log",
    }
  )
);
