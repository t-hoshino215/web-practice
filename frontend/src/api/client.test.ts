import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { buildMessage } from '../../tests/factories/models';
import { ApiError, getCsrfToken, request } from './client';
import { messageSchema } from './schemas';

/**
 * fetchの戻り値を最小限で模したヘルパー。
 * jsdom環境ではResponseの実体があるとは限らないため、必要なプロパティだけを持つ値を使う。
 */
function stubResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

describe('client', () => {
  describe('getCsrfToken', () => {
    it('should read and decode the CSRF cookie', () => {
      // Arrange
      document.cookie = 'csrf_token=token%20value; Path=/';

      // Act & Assert
      expect(getCsrfToken()).toBe('token value');
    });

    it('should match the complete cookie name', () => {
      // Arrange
      document.cookie = 'prefixed_csrf_token=wrong-token; Path=/';

      // Act & Assert
      expect(getCsrfToken()).toBeNull();
    });

    it('should return null when the cookie contains invalid percent encoding', () => {
      // Arrange
      document.cookie = 'csrf_token=%invalid; Path=/';

      // Act & Assert
      expect(getCsrfToken()).toBeNull();
    });
  });

  describe('request', () => {
    beforeEach(() => {
      vi.stubGlobal('fetch', vi.fn());
    });

    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it('should return the validated payload when the response matches the schema', async () => {
      // Arrange
      const message = buildMessage();
      vi.mocked(fetch).mockResolvedValue(stubResponse(message));

      // Act
      const result = await request('/messages/1', messageSchema);

      // Assert
      expect(result).toEqual(message);
    });

    it('should prefix the path with /api when calling fetch', async () => {
      // Arrange
      vi.mocked(fetch).mockResolvedValue(stubResponse(buildMessage()));

      // Act
      await request('/messages/1', messageSchema);

      // Assert
      expect(fetch).toHaveBeenCalledWith('/api/messages/1', expect.anything());
    });

    it('should send the X-CSRF-Token header when csrf is required', async () => {
      // Arrange
      document.cookie = 'csrf_token=test-token; Path=/';
      vi.mocked(fetch).mockResolvedValue(stubResponse(buildMessage()));

      // Act
      await request('/messages', messageSchema, {
        method: 'POST',
        body: { text: 'hi' },
        csrf: true,
      });

      // Assert
      expect(fetch).toHaveBeenCalledWith(
        '/api/messages',
        expect.objectContaining({
          headers: expect.objectContaining({ 'X-CSRF-Token': 'test-token' }),
        }),
      );
    });

    it('should throw ApiError before sending when csrf is required but no token is stored', async () => {
      // Act & Assert
      await expect(
        request('/messages', messageSchema, { method: 'POST', csrf: true }),
      ).rejects.toBeInstanceOf(ApiError);
    });

    it('should throw ApiError carrying the status when the API returns an error', async () => {
      // Arrange
      vi.mocked(fetch).mockResolvedValue(stubResponse({ detail: 'Username already exists' }, 409));

      // Act & Assert
      await expect(request('/users', messageSchema, { method: 'POST' })).rejects.toMatchObject({
        status: 409,
        message: 'Username already exists',
      });
    });

    it('should join field names and messages when the API returns a 422 validation error', async () => {
      // Arrange
      const detail = [
        { loc: ['body', 'username'], msg: 'String should have at least 3 characters' },
        { loc: ['body', 'password'], msg: 'String should have at least 8 characters' },
      ];
      vi.mocked(fetch).mockResolvedValue(stubResponse({ detail }, 422));

      // Act & Assert
      await expect(request('/users', messageSchema, { method: 'POST' })).rejects.toThrowError(
        'username: String should have at least 3 characters / password: String should have at least 8 characters',
      );
    });

    it.each([
      ['HTMLが返った場合', null],
      ['detailが無い場合', {}],
    ])(
      'should fall back to a generic message when the error body is unusable: %s',
      async (_label, body) => {
        // Arrange
        vi.mocked(fetch).mockResolvedValue(stubResponse(body, 500));

        // Act & Assert
        await expect(request('/messages', messageSchema)).rejects.toThrowError(
          'リクエストに失敗しました (HTTP 500)',
        );
      },
    );
  });
});
