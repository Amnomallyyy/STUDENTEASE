// UI session state that is not part of the Profile contract: map filters, the pinned job, roadmap tick-offs,
// the chat transcript and the action the chatbot last asked the UI to perform.
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ChatAction, UIMessage } from "../types/api";

export const RADIUS_OPTIONS = [5, 10, 25] as const;
export const DEFAULT_RADIUS_KM = 25;
export const DEFAULT_MATCH_WEIGHT = 0.7;

interface SessionState {
  role: string | null;
  radiusKm: number;
  minMatch: number;
  keyword: string;
  matchWeight: number;
  showKeywordMatch: boolean;
  pinnedJobId: string | null;
  selectedJobId: string | null;
  roadmapDone: Record<string, boolean>;
  chatOpen: boolean;
  messages: UIMessage[];
  pendingAction: ChatAction | null;
  serverExpired: boolean;

  setRole: (role: string | null) => void;
  setRadiusKm: (radiusKm: number) => void;
  setMinMatch: (minMatch: number) => void;
  setKeyword: (keyword: string) => void;
  setMatchWeight: (matchWeight: number) => void;
  setShowKeywordMatch: (show: boolean) => void;
  setPinnedJobId: (id: string | null) => void;
  setSelectedJobId: (id: string | null) => void;
  toggleTask: (key: string) => void;
  resetProgress: () => void;
  setChatOpen: (open: boolean) => void;
  setMessages: (messages: UIMessage[]) => void;
  clearChat: () => void;
  setPendingAction: (action: ChatAction | null) => void;
  setServerExpired: (expired: boolean) => void;
  reset: () => void;
}

/** The chat column is open by default on wide screens; on a phone it is a full-screen overlay, so start closed. */
const wideScreen = typeof window !== "undefined" && typeof window.matchMedia === "function"
  ? window.matchMedia("(min-width: 1024px)").matches
  : true;

const initial = {
  role: null,
  radiusKm: DEFAULT_RADIUS_KM,
  minMatch: 0,
  keyword: "",
  matchWeight: DEFAULT_MATCH_WEIGHT,
  showKeywordMatch: false,
  pinnedJobId: null,
  selectedJobId: null,
  roadmapDone: {},
  chatOpen: wideScreen,
  messages: [],
  pendingAction: null,
  serverExpired: false,
};

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      ...initial,
      setRole: (role) => set({ role, pinnedJobId: null, selectedJobId: null }),
      setRadiusKm: (radiusKm) => set({ radiusKm }),
      setMinMatch: (minMatch) => set({ minMatch }),
      setKeyword: (keyword) => set({ keyword }),
      setMatchWeight: (matchWeight) => set({ matchWeight }),
      setShowKeywordMatch: (showKeywordMatch) => set({ showKeywordMatch }),
      setPinnedJobId: (pinnedJobId) => set({ pinnedJobId }),
      setSelectedJobId: (selectedJobId) => set({ selectedJobId }),
      toggleTask: (key) => set((s) => ({ roadmapDone: { ...s.roadmapDone, [key]: !s.roadmapDone[key] } })),
      resetProgress: () => set({ roadmapDone: {} }),
      setChatOpen: (chatOpen) => set({ chatOpen }),
      setMessages: (messages) => set({ messages }),
      clearChat: () => set({ messages: [], pendingAction: null }),
      setPendingAction: (pendingAction) => set({ pendingAction }),
      setServerExpired: (serverExpired) => set({ serverExpired }),
      reset: () => set({ ...initial }),
    }),
    {
      name: "careerlens-session",
      version: 1,
      partialize: (s) => ({
        role: s.role,
        radiusKm: s.radiusKm,
        minMatch: s.minMatch,
        matchWeight: s.matchWeight,
        showKeywordMatch: s.showKeywordMatch,
        pinnedJobId: s.pinnedJobId,
        roadmapDone: s.roadmapDone,
        chatOpen: s.chatOpen,
        messages: s.messages,
      }),
    },
  ),
);

/** Key for a roadmap task's local tick-off (progress is stored in the browser only). */
export function taskKey(role: string | null, week: number, title: string): string {
  return `${role ?? ""}|${week}|${title}`;
}
