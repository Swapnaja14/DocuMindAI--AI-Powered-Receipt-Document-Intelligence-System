import { useState, useEffect } from 'react';

/**
 * Robustly parses a date input (ISO string, unix ms, Date) and ensures
 * it is accurately synchronized with the client device's local timezone.
 *
 * Backend/MongoDB timestamps often lack the 'Z' indicator (e.g. "2026-10-19T14:45:00.123456").
 * Without 'Z', standard JavaScript Date parsing erroneously treats it as local time,
 * causing timezone skew (e.g. 5 hours and 30 minutes in the past for IST).
 */
export function parseToDeviceDate(dateInput) {
  if (!dateInput) return new Date();
  if (dateInput instanceof Date) return dateInput;
  if (typeof dateInput === 'number') {
    return new Date(dateInput < 1e11 ? dateInput * 1000 : dateInput);
  }

  let str = String(dateInput).trim();
  if (!str) return new Date();

  // If numeric string timestamp
  if (/^\d+$/.test(str)) {
    const num = Number(str);
    return new Date(num < 1e11 ? num * 1000 : num);
  }

  // If ISO string without timezone offset or Z, explicitly append Z to treat as UTC
  // e.g. "2026-10-19T15:18:24" or "2026-10-19T15:18:24.123456"
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$/.test(str)) {
    str += 'Z';
  } else if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d+)?$/.test(str)) {
    str = str.replace(' ', 'T') + 'Z';
  }

  const parsed = new Date(str);
  return isNaN(parsed.getTime()) ? new Date() : parsed;
}

/**
 * Formats time in the device's local clock (e.g., "8:45:16 PM")
 */
export function formatDeviceTime(dateInput, includeSeconds = true) {
  const d = parseToDeviceDate(dateInput);
  return d.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: includeSeconds ? '2-digit' : undefined,
    hour12: true,
  });
}

/**
 * Formats date in the device's local calendar (e.g., "Oct 19, 2026")
 */
export function formatDeviceDate(dateInput) {
  const d = parseToDeviceDate(dateInput);
  const now = new Date();
  return d.toLocaleDateString([], {
    month: 'short',
    day: 'numeric',
    year: d.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  });
}

/**
 * Formats full timestamp in device locale with date and time
 */
export function formatDeviceDateTime(dateInput) {
  const d = parseToDeviceDate(dateInput);
  return `${formatDeviceDate(d)} at ${formatDeviceTime(d, true)}`;
}

/**
 * Calculates live dynamic relative time from now (e.g. "Just now", "12s ago", "2m ago")
 * perfectly synchronized with the user's device clock.
 */
export function formatDynamicRelativeTime(dateInput, now = Date.now()) {
  if (!dateInput) return 'Recently';

  const date = parseToDeviceDate(dateInput);
  const nowMs = typeof now === 'number' ? now : new Date(now).getTime();
  const diffInSeconds = Math.max(0, Math.floor((nowMs - date.getTime()) / 1000));

  if (diffInSeconds < 5) return 'Just now';
  if (diffInSeconds < 60) return `${diffInSeconds}s ago`;

  const diffInMinutes = Math.floor(diffInSeconds / 60);
  if (diffInMinutes < 60) {
    return `${diffInMinutes}m ago`;
  }

  const diffInHours = Math.floor(diffInMinutes / 60);
  if (diffInHours < 24) {
    return `${diffInHours}h ago`;
  }

  const diffInDays = Math.floor(diffInHours / 24);
  if (diffInDays < 7) {
    return `${diffInDays}d ago`;
  }

  return formatDeviceDate(date);
}

/**
 * Calculates dynamic elapsed processing time duration (e.g. "8s", "45s", "1m 12s")
 */
export function formatProcessingElapsed(dateInput, now = Date.now()) {
  if (!dateInput) return '';

  const date = parseToDeviceDate(dateInput);
  const nowMs = typeof now === 'number' ? now : new Date(now).getTime();
  const diffInSeconds = Math.max(0, Math.floor((nowMs - date.getTime()) / 1000));

  if (diffInSeconds < 60) return `${diffInSeconds}s`;
  const mins = Math.floor(diffInSeconds / 60);
  const secs = diffInSeconds % 60;
  return `${mins}m ${secs}s`;
}

/**
 * React hook that yields current device time updating every `intervalMs` ms.
 * Allows components to reactively update relative times and pipeline statuses
 * dynamically as time passes.
 */
export function useLiveDeviceTime(intervalMs = 1000) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = setInterval(() => {
      setNow(Date.now());
    }, intervalMs);

    return () => clearInterval(timer);
  }, [intervalMs]);

  return now;
}
