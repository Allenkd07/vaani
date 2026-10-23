import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";

// Keep in sync with the inline script in index.html, which applies the theme before first paint.
const STORAGE_KEY = "vaani-theme";
const THEME_COLORS: Record<Theme, string> = { light: "#ffffff", dark: "#202124" };
const systemQuery = () => window.matchMedia("(prefers-color-scheme: dark)");

function readStored(): Theme | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

function apply(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_COLORS[theme]);
}

/** Follows the system theme until the user picks one; the choice is remembered per browser. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => (document.documentElement.dataset.theme === "dark" ? "dark" : "light"));

  useEffect(() => {
    apply(theme);
  }, [theme]);

  useEffect(() => {
    if (readStored()) return;
    const query = systemQuery();
    const onChange = (event: MediaQueryListEvent) => setTheme(event.matches ? "dark" : "light");
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  const toggle = useCallback(() => {
    setTheme((current) => {
      const next = current === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        // Storage can be unavailable (private mode); the choice then lasts for this page only.
      }
      return next;
    });
  }, []);

  return { theme, toggle };
}
