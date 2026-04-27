"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useSyncExternalStore,
} from "react";

type Theme = "light" | "dark";

type ThemeContextValue = {
  resolvedTheme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
};

const STORAGE_KEY = "fundingpulse-theme";
const THEME_CHANGE_EVENT = "fundingpulse-theme-change";

const ThemeContext = createContext<ThemeContextValue | null>(null);

function isTheme(value: string | undefined): value is Theme {
  return value === "light" || value === "dark";
}

function getPreferredTheme(): Theme {
  if (typeof window === "undefined") {
    return "dark";
  }

  const storedTheme = window.localStorage.getItem(STORAGE_KEY);
  if (storedTheme === "light" || storedTheme === "dark") {
    return storedTheme;
  }

  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function getThemeSnapshot(): Theme {
  const documentTheme = document.documentElement.dataset.theme;
  return isTheme(documentTheme) ? documentTheme : getPreferredTheme();
}

function getServerThemeSnapshot(): Theme {
  return "dark";
}

function subscribeToThemeChange(onStoreChange: () => void) {
  function handleStorageChange(event: StorageEvent) {
    if (event.key === STORAGE_KEY) {
      onStoreChange();
    }
  }

  window.addEventListener(THEME_CHANGE_EVENT, onStoreChange);
  window.addEventListener("storage", handleStorageChange);

  return () => {
    window.removeEventListener(THEME_CHANGE_EVENT, onStoreChange);
    window.removeEventListener("storage", handleStorageChange);
  };
}

function writeTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  window.localStorage.setItem(STORAGE_KEY, theme);
  window.dispatchEvent(new Event(THEME_CHANGE_EVENT));
}

type ThemeProviderProps = {
  children: ReactNode;
};

export function ThemeProvider({ children }: ThemeProviderProps) {
  const resolvedTheme = useSyncExternalStore(
    subscribeToThemeChange,
    getThemeSnapshot,
    getServerThemeSnapshot,
  );

  const setTheme = useCallback((theme: Theme) => {
    writeTheme(theme);
  }, []);

  const toggleTheme = useCallback(() => {
    writeTheme(getThemeSnapshot() === "dark" ? "light" : "dark");
  }, []);

  const value: ThemeContextValue = useMemo(
    () => ({
      resolvedTheme,
      setTheme,
      toggleTheme,
    }),
    [resolvedTheme, setTheme, toggleTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);

  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }

  return context;
}
