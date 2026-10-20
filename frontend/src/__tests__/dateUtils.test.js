import { describe, it, expect } from 'vitest';
import {
  parseToDeviceDate,
  formatDeviceDate,
  formatDeviceTime,
  formatDeviceDateTime,
  formatDynamicRelativeTime,
  formatProcessingElapsed,
} from '../features/documents/utils/dateUtils';

describe('Document Date & Timezone Utilities', () => {
  it('handles null/undefined date inputs gracefully', () => {
    const result = parseToDeviceDate(null);
    expect(result).toBeInstanceOf(Date);
    expect(isNaN(result.getTime())).toBe(false);
  });

  it('correctly appends UTC "Z" indicator when ISO string lacks timezone offset', () => {
    const rawMongoDate = '2026-10-19T14:30:00';
    const parsed = parseToDeviceDate(rawMongoDate);
    expect(parsed.toISOString()).toBe('2026-10-19T14:30:00.000Z');
  });

  it('correctly parses space-delimited datetime strings without timezone', () => {
    const rawMongoDate = '2026-10-19 14:30:00';
    const parsed = parseToDeviceDate(rawMongoDate);
    expect(parsed.toISOString()).toBe('2026-10-19T14:30:00.000Z');
  });

  it('formats device local time and date', () => {
    const isoString = '2026-10-19T12:00:00Z';
    const formattedDate = formatDeviceDate(isoString);
    expect(typeof formattedDate).toBe('string');
    expect(formattedDate.length).toBeGreaterThan(0);

    const formattedTime = formatDeviceTime(isoString);
    expect(typeof formattedTime).toBe('string');
    expect(formattedTime).toMatch(/\d{1,2}:\d{2}(:\d{2})?\s*(AM|PM)?/i);

    const formattedDateTime = formatDeviceDateTime(isoString);
    expect(typeof formattedDateTime).toBe('string');
    expect(formattedDateTime.length).toBeGreaterThan(0);
  });

  it('formats relative elapsed time accurately', () => {
    const nowMs = 1760000000000;
    // 2 seconds ago
    const justNow = new Date(nowMs - 2 * 1000).toISOString();
    expect(formatDynamicRelativeTime(justNow, nowMs)).toBe('Just now');

    // 15 seconds ago
    const secondsAgo = new Date(nowMs - 15 * 1000).toISOString();
    expect(formatDynamicRelativeTime(secondsAgo, nowMs)).toBe('15s ago');

    // 5 minutes ago
    const fiveMinAgo = new Date(nowMs - 5 * 60 * 1000).toISOString();
    expect(formatDynamicRelativeTime(fiveMinAgo, nowMs)).toBe('5m ago');

    // 2 hours ago
    const twoHoursAgo = new Date(nowMs - 2 * 60 * 60 * 1000).toISOString();
    expect(formatDynamicRelativeTime(twoHoursAgo, nowMs)).toBe('2h ago');

    // 3 days ago
    const threeDaysAgo = new Date(nowMs - 3 * 24 * 60 * 60 * 1000).toISOString();
    expect(formatDynamicRelativeTime(threeDaysAgo, nowMs)).toBe('3d ago');
  });

  it('formats processing elapsed time string', () => {
    const nowMs = 1760000000000;
    const thirtySecs = new Date(nowMs - 30 * 1000).toISOString();
    expect(formatProcessingElapsed(thirtySecs, nowMs)).toBe('30s');

    const twoMinsTenSecs = new Date(nowMs - 130 * 1000).toISOString();
    expect(formatProcessingElapsed(twoMinsTenSecs, nowMs)).toBe('2m 10s');
  });
});
