"use client";

import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useState,
} from "react";

type Theme = "light" | "dark";

type ThemeContextValue = {
  resolvedTheme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
};

const STORAGE_KEY = "fundingpulse-theme";

const ThemeContext = createContext<ThemeContextValue | null>(null);

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

type ThemeProviderProps = {
  children: ReactNode;
};

export function ThemeProvider({ children }: ThemeProviderProps) {
  const [resolvedTheme, setResolvedTheme] = useState<Theme>(() => {
    if (typeof document !== "undefined") {
      const documentTheme = document.documentElement.dataset.theme;
      if (documentTheme === "light" || documentTheme === "dark") {
        return documentTheme;
      }
    }

    return getPreferredTheme();
  });

  useEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme;
    window.localStorage.setItem(STORAGE_KEY, resolvedTheme);
  }, [resolvedTheme]);

  const value: ThemeContextValue = {
    resolvedTheme,
    setTheme: setResolvedTheme,
    toggleTheme: () => {
      setResolvedTheme((currentTheme) => (currentTheme === "dark" ? "light" : "dark"));
    },
  };

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);

  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }

  return context;
}
