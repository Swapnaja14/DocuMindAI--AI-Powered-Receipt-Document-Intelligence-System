import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  apiClient,
  setAuthToken,
  getAuthToken,
  resolveApiUrl,
  BASE_URL,
} from '../api/client';

describe('API Client & Base URL Configuration', () => {
  let mockStorage = {};
  let originalWindow = globalThis.window;
  let originalSessionStorage = globalThis.sessionStorage;

  beforeEach(() => {
    mockStorage = {};
    globalThis.sessionStorage = {
      getItem: (key) => mockStorage[key] || null,
      setItem: (key, val) => { mockStorage[key] = String(val); },
      removeItem: (key) => { delete mockStorage[key]; },
      clear: () => { mockStorage = {}; },
    };

    globalThis.window = {
      dispatchEvent: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    };

    setAuthToken(null);
    vi.restoreAllMocks();
  });

  afterEach(() => {
    setAuthToken(null);
    globalThis.window = originalWindow;
    globalThis.sessionStorage = originalSessionStorage;
  });

  it('normalizes base URL and resolves endpoints accurately', () => {
    expect(BASE_URL).toBeDefined();
    expect(BASE_URL.endsWith('/')).toBe(false);

    // Relative paths
    expect(resolveApiUrl('/documents')).toBe(`${BASE_URL}/documents`);
    expect(resolveApiUrl('documents')).toBe(`${BASE_URL}/documents`);

    // Absolute URLs pass through unchanged
    expect(resolveApiUrl('https://api.documind.ai/v1/health')).toBe(
      'https://api.documind.ai/v1/health'
    );
  });

  it('manages auth tokens in-memory and in sessionStorage', () => {
    expect(getAuthToken()).toBeNull();

    setAuthToken('mock-jwt-token-12345');
    expect(getAuthToken()).toBe('mock-jwt-token-12345');

    setAuthToken(null);
    expect(getAuthToken()).toBeNull();
  });

  it('attaches Authorization Bearer header when token is set', async () => {
    setAuthToken('test-secret-token');

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ status: 'success' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const result = await apiClient('/users/me');
    expect(result).toEqual({ status: 'success' });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    const callArgs = fetchMock.mock.calls[0];
    expect(callArgs[0]).toBe(`${BASE_URL}/users/me`);
    expect(callArgs[1].headers['Authorization']).toBe('Bearer test-secret-token');
    expect(callArgs[1].headers['Content-Type']).toBe('application/json');
  });

  it('omits Content-Type header when request body is FormData', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ id: 'doc-123' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const formData = new FormData();
    formData.append('sample', 'value');

    await apiClient('/documents/upload', {
      method: 'POST',
      body: formData,
    });

    const callArgs = fetchMock.mock.calls[0];
    expect(callArgs[1].headers['Content-Type']).toBeUndefined();
  });

  it('returns empty object without JSON parsing for 204 No Content', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      headers: new Headers(),
    });
    vi.stubGlobal('fetch', fetchMock);

    const result = await apiClient('/documents/doc-123', {
      method: 'DELETE',
    });
    expect(result).toEqual({});
  });

  it('dispatches unauthorized event and throws clean error on 401', async () => {
    const dispatchSpy = vi.spyOn(globalThis.window, 'dispatchEvent');

    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ detail: 'Invalid credentials or expired token' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiClient('/protected')).rejects.toMatchObject({
      status: 401,
      message: 'Invalid credentials or expired token',
    });

    expect(dispatchSpy).toHaveBeenCalled();
  });

  it('formats FastAPI validation error details cleanly on 422', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({
        detail: [
          { loc: ['body', 'question'], msg: 'Field required' },
          { loc: ['body', 'top_k'], msg: 'Value must be between 1 and 10' },
        ],
      }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiClient('/rag/ask')).rejects.toMatchObject({
      status: 422,
      message: 'question: Field required; top_k: Value must be between 1 and 10',
    });
  });
});
