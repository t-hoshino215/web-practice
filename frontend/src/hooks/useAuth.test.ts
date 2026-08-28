import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { buildUser } from '../../tests/factories/models';
import * as authApi from '../api/auth';
import { useAuth } from './useAuth';

vi.mock('../api/auth', () => ({
  fetchCurrentUser: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  refreshCsrf: vi.fn(),
  registerUser: vi.fn(),
}));

describe('useAuth', () => {
  beforeEach(() => {
    vi.mocked(authApi.fetchCurrentUser).mockResolvedValue(buildUser());
    vi.mocked(authApi.refreshCsrf).mockResolvedValue();
  });

  describe('session restoration', () => {
    it('should authenticate without refreshing when the CSRF cookie exists', async () => {
      // Arrange
      document.cookie = 'csrf_token=existing-token; Path=/';

      // Act
      const { result } = renderHook(() => useAuth());
      await waitFor(() => expect(result.current.status).toBe('authenticated'));

      // Assert
      expect(authApi.refreshCsrf).not.toHaveBeenCalled();
    });

    it('should refresh before authenticating when the CSRF cookie is missing', async () => {
      // Act
      const { result } = renderHook(() => useAuth());
      await waitFor(() => expect(result.current.status).toBe('authenticated'));

      // Assert
      expect(authApi.refreshCsrf).toHaveBeenCalledOnce();
    });

    it('should become anonymous when refreshing a missing CSRF cookie fails', async () => {
      // Arrange
      vi.mocked(authApi.refreshCsrf).mockRejectedValue(new Error('refresh failed'));

      // Act
      const { result } = renderHook(() => useAuth());
      await waitFor(() => expect(result.current.status).toBe('anonymous'));

      // Assert
      expect(result.current.bootstrapNotice).not.toBeNull();
    });
  });
});
