import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { refreshCsrf } from './auth';

function stubNoContentResponse(): Response {
  return {
    ok: true,
    status: 204,
  } as Response;
}

describe('auth', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(stubNoContentResponse()));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('refreshCsrf', () => {
    it('should request a new CSRF cookie for the current session', async () => {
      // Act
      await refreshCsrf();

      // Assert
      expect(fetch).toHaveBeenCalledWith(
        '/api/auth/csrf',
        expect.objectContaining({ method: 'POST', credentials: 'same-origin' }),
      );
    });
  });
});
