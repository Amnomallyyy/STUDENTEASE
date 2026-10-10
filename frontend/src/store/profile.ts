// Zustand store mirroring the shared Profile object (backend/schemas/profile.py), persisted to local storage
// so a reload keeps the dashboard. The server keeps its own in-memory copy; "Delete my data" clears both.
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { Profile } from "../types/profile";

interface ProfileState {
  profile: Profile | null;
  updatedAt: number | null;
  setProfile: (profile: Profile) => void;
  merge: (patch: Partial<Profile>) => void;
  clear: () => void;
}

export const useProfileStore = create<ProfileState>()(
  persist(
    (set) => ({
      profile: null,
      updatedAt: null,
      setProfile: (profile) => set({ profile, updatedAt: Date.now() }),
      merge: (patch) =>
        set((state) =>
          state.profile ? { profile: { ...state.profile, ...patch }, updatedAt: Date.now() } : state,
        ),
      clear: () => set({ profile: null, updatedAt: null }),
    }),
    // sessionStorage: a profile lives only in the tab that uploaded the CV, so every visitor starts fresh.
    { name: "careerlens-profile", version: 1, storage: createJSONStorage(() => window.sessionStorage) },
  ),
);

export function hasCV(profile: Profile | null): profile is Profile {
  return !!profile && profile.skills.length > 0;
}
