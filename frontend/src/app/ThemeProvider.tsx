import { createContext, useContext, useEffect, useState } from "react";
import type { PropsWithChildren } from "react";

export type Theme = "light" | "dark";

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);
const THEME_KEY = "datatrace-theme-v1";

function readTheme(): Theme {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(THEME_KEY) ?? "null");
    if (typeof value === "object" && value !== null && "theme" in value) {
      return value.theme === "dark" ? "dark" : "light";
    }
  } catch {
    localStorage.removeItem(THEME_KEY);
  }
  return "light";
}

export function ThemeProvider({ children }: PropsWithChildren) {
  const [theme, setTheme] = useState<Theme>(readTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(THEME_KEY, JSON.stringify({ version: 1, theme }));
  }, [theme]);

  function toggleTheme() {
    setTheme((current) => current === "light" ? "dark" : "light");
  }

  return <ThemeContext.Provider value={{ theme, toggleTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used within ThemeProvider.");
  return context;
}
