export function asText(value: unknown, fallback = "Unavailable") {
  if (typeof value === "string") {
    return value || fallback;
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  return fallback;
}

export function asNumber(value: unknown, fallback = 0) {
  const num = Number(value ?? fallback);
  return Number.isFinite(num) ? num : fallback;
}

export function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? value : [];
}

export function asDateText(value: unknown, fallback = "Unknown") {
  if (!value) {
    return fallback;
  }

  const text = typeof value === "string" ? value : String(value);
  const date = new Date(text);
  return Number.isNaN(date.getTime()) ? text || fallback : date.toLocaleString();
}

