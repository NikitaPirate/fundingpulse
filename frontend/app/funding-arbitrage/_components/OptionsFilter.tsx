"use client";

import { useMemo, useState } from "react";

import styles from "../page.module.css";
import type { FilterOption } from "../_lib/types";
import { FilterPopover } from "./FilterPopover";

type OptionsFilterProps =
  | {
      label: string;
      options: FilterOption[];
      value: string[];
      multiple: true;
      active?: boolean;
      loading?: boolean;
      onChange: (value: string[]) => void;
      searchPlaceholder?: string;
      emptyLabel?: string;
    }
  | {
      label: string;
      options: FilterOption[];
      value: string | null;
      multiple: false;
      active?: boolean;
      loading?: boolean;
      onChange: (value: string | null) => void;
      searchPlaceholder?: string;
      emptyLabel?: string;
    };

function summarizeValue(props: OptionsFilterProps) {
  if (props.multiple) {
    if (props.value.length === 0) {
      return "All";
    }

    if (props.value.length === 1) {
      return props.value[0];
    }

    return `${props.value.length} selected`;
  }

  return props.value ?? "All";
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
