import { create } from "zustand";
import themeDark from "./theme_dark";
import themeLight from "./theme_light";

// Global theme store with persisted mode and toggle action.
export const useThemeStore = create((set) => ({
  themeMode: localStorage.getItem("themeMode") || "light",
  theme: localStorage.getItem("themeMode") === "dark" ? themeDark : themeLight,

  // Flip between light/dark and persist the new mode.
  toggleTheme: () =>
    set((state) => {
      const nextMode = state.themeMode === "light" ? "dark" : "light";
      const nextTheme = nextMode === "dark" ? themeDark : themeLight;

      localStorage.setItem("themeMode", nextMode);

      return {
        themeMode: nextMode,
        theme: nextTheme,
      };
    }),
}));
