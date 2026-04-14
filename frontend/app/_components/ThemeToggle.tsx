"use client";

import { useTheme } from "../_theme/ThemeProvider";
import styles from "./ThemeToggle.module.css";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();

  return (
    <div aria-label="Theme" className={styles.toggle} role="group">
      <button
        aria-pressed={resolvedTheme === "light"}
        className={resolvedTheme === "light" ? styles.optionActive : styles.option}
        onClick={() => setTheme("light")}
        type="button"
      >
        Light
      </button>
      <button
        aria-pressed={resolvedTheme === "dark"}
        className={resolvedTheme === "dark" ? styles.optionActive : styles.option}
        onClick={() => setTheme("dark")}
        type="button"
      >
        Dark
      </button>
    </div>
  );
}
