"use client";

import { useMemo, useState } from "react";

import { FilterPopover } from "./FilterPopover";
import styles from "./filterControls.module.css";

export type FilterOption = {
  value: string;
  label: string;
};

type BaseProps = {
  label: string;
  options: FilterOption[];
  active?: boolean;
  loading?: boolean;
  searchPlaceholder?: string;
  emptyLabel?: string;
  emptySummary?: string;
};

type OptionsFilterProps =
  | (BaseProps & {
      value: string[];
      multiple: true;
      onChange: (value: string[]) => void;
    })
  | (BaseProps & {
      value: string | null;
      multiple: false;
      onChange: (value: string | null) => void;
    });

function summarizeValue(props: OptionsFilterProps) {
  if (props.multiple) {
    if (props.value.length === 0) {
      return props.emptySummary ?? "All";
    }

    if (props.value.length === 1) {
      return props.value[0];
    }

    return `${props.value.length} selected`;
  }

  return props.value ?? props.emptySummary ?? "All";
}

export function OptionsFilter(props: OptionsFilterProps) {
  const [searchValue, setSearchValue] = useState("");

  const filteredOptions = useMemo(() => {
    const normalizedQuery = searchValue.trim().toLowerCase();

    if (!normalizedQuery) {
      return props.options;
    }

    return props.options.filter((option) =>
      option.label.toLowerCase().includes(normalizedQuery),
    );
  }, [props.options, searchValue]);

  return (
    <FilterPopover
      active={
        props.active ?? (props.multiple ? props.value.length > 0 : props.value !== null)
      }
      label={props.label}
      summary={summarizeValue(props)}
    >
      {({ close }) => (
        <>
          <div className={styles.panelHeader}>
            <strong className={styles.panelTitle}>{props.label}</strong>
            <button
              className={styles.panelAction}
              onClick={() => {
                if (props.multiple) {
                  props.onChange([]);
                } else {
                  props.onChange(null);
                  close();
                }
              }}
              type="button"
            >
              Clear
            </button>
          </div>

          <input
            className={styles.filterSearch}
            onChange={(event) => setSearchValue(event.target.value)}
            placeholder={props.searchPlaceholder ?? "Search..."}
            type="search"
            value={searchValue}
          />

          <div className={styles.optionList}>
            {props.loading ? (
              <span className={styles.optionEmpty}>Loading options...</span>
            ) : filteredOptions.length === 0 ? (
              <span className={styles.optionEmpty}>
                {props.emptyLabel ?? "No matching options"}
              </span>
            ) : null}

            {filteredOptions.map((option) => {
              const selected = props.multiple
                ? props.value.includes(option.value)
                : props.value === option.value;

              return (
                <label className={styles.optionRow} key={option.value}>
                  <input
                    checked={selected}
                    className={styles.optionInput}
                    name={`${props.label}-${option.value}`}
                    onChange={() => {
                      if (props.multiple) {
                        if (selected) {
                          props.onChange(
                            props.value.filter((value) => value !== option.value),
                          );
                        } else {
                          props.onChange([...props.value, option.value]);
                        }

                        return;
                      }

                      props.onChange(selected ? null : option.value);
                      close();
                    }}
                    type={props.multiple ? "checkbox" : "radio"}
                  />
                  <span className={styles.optionLabel}>{option.label}</span>
                </label>
              );
            })}
          </div>
        </>
      )}
    </FilterPopover>
  );
}
