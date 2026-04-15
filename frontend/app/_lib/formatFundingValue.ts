export function formatFundingValue(value: number) {
  const percentage = value * 100;
  const absValue = Math.abs(percentage);
  const sign = percentage >= 0 ? "+" : "-";

  if (absValue >= 1) {
    return `${sign}${absValue.toFixed(2)}%`;
  }

  if (absValue >= 0.1) {
    return `${sign}${absValue.toFixed(3)}%`;
  }

  return `${sign}${absValue.toFixed(4)}%`;
}
