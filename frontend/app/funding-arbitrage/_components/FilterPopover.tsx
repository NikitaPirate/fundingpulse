"use client";

import { type ReactNode, useEffect, useId, useRef, useState } from "react";

import styles from "../page.module.css";

type FilterPopoverProps = {
  label: string;
  summary: ReactNode;
  active?: boolean;
  disabled?: boolean;
  panelClassName?: string;
  children: (controls: { close: () => void }) => ReactNode;
};

export function FilterPopover({
  label,
  summary,
  active = false,
  disabled = false,
  panelClassName,
  children,
}: FilterPopoverProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) {
      return;
    }

    function handlePointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  return (
    <div className={styles.filterPopover} ref={containerRef}>
      <button
        aria-controls={panelId}
        aria-expanded={open}
        className={`${styles.filterTrigger} ${active ? styles.filterTriggerActive : ""}`}
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
        type="button"
      >
        <span className={styles.filterLabel}>{label}</span>
        <span className={styles.filterSummary}>{summary}</span>
      </button>

      {open ? (
        <div
          className={`${styles.filterPanel} ${panelClassName ?? ""}`}
          id={panelId}
          role="dialog"
        >
          {children({
            close: () => setOpen(false),
          })}
        </div>
      ) : null}
    </div>
  );
}
