import { useState, useEffect } from 'react';

/**
 * Returns a debounced copy of `value`.
 * The returned value only updates after the caller stops
 * changing `value` for `delayMs` milliseconds.
 */
export function useDebounce<T>(value: T, delayMs: number = 300): T {
  const [debounced, setDebounced] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
