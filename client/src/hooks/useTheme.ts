import { useState, useEffect, useCallback } from "react";

/** Theme mode options for dark mode control. */
export const ThemeMode = {
  LIGHT: "light",
  DARK: "dark",
  SYSTEM: "system",
} as const;

export type ThemeMode = (typeof ThemeMode)[keyof typeof ThemeMode];

const STORAGE_KEY = "theme";

interface ThemeState {
  mode: ThemeMode;
  isDark: boolean;
  setMode: (mode: ThemeMode) => void;
}

/** Read initial mode from localStorage, defaulting to SYSTEM. */
function readStoredMode(): ThemeMode {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === ThemeMode.LIGHT) {
    return ThemeMode.LIGHT;
  }
  if (stored === ThemeMode.DARK) {
    return ThemeMode.DARK;
  }
  return ThemeMode.SYSTEM;
}

/** Check if the system prefers dark mode. */
function getSystemPrefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/**
 * Dark mode state with localStorage persistence and system preference detection.
 *
 * On first visit with no stored preference, defaults to SYSTEM (follows OS).
 * Syncs the `.dark` class on `document.documentElement` whenever isDark changes.
 * Listens for system preference changes when in SYSTEM mode.
 */
export function useTheme(): ThemeState {
  const [mode, setModeState] = useState<ThemeMode>(readStoredMode);
  const [systemPrefersDark, setSystemPrefersDark] = useState<boolean>(getSystemPrefersDark);

  // Compute isDark from mode and system preference
  let isDark: boolean;
  switch (mode) {
    case ThemeMode.LIGHT:
      isDark = false;
      break;
    case ThemeMode.DARK:
      isDark = true;
      break;
    case ThemeMode.SYSTEM:
      isDark = systemPrefersDark;
      break;
  }

  // Sync .dark class on documentElement
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [isDark]);

  // Listen for system preference changes when in SYSTEM mode
  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

    function handleChange(e: MediaQueryListEvent): void {
      setSystemPrefersDark(e.matches);
    }

    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  const setMode = useCallback((newMode: ThemeMode): void => {
    setModeState(newMode);
    if (newMode === ThemeMode.SYSTEM) {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY, newMode);
    }
  }, []);

  return { mode, isDark, setMode };
}
