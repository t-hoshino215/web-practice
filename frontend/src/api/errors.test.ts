import { describe, expect, it } from 'vitest';
import { ZodError } from 'zod';

import { ApiError } from './client';
import { isUnauthorized, toMessage } from './errors';

describe('errors', () => {
  describe('toMessage', () => {
    it('should return the API message when the error is an ApiError', () => {
      // Arrange
      const error = new ApiError(409, 'Username already exists');

      // Act & Assert
      expect(toMessage(error)).toBe('Username already exists');
    });

    it('should return the schema mismatch message when the error is a ZodError', () => {
      // Act & Assert
      expect(toMessage(new ZodError([]))).toContain('サーバーの応答形式');
    });

    it('should return the network message when the error is unknown', () => {
      // Act & Assert
      expect(toMessage(new TypeError('Failed to fetch'))).toContain(
        'サーバーに接続できませんでした',
      );
    });
  });

  describe('isUnauthorized', () => {
    it.each([
      [401, true],
      [403, false],
      [500, false],
    ])('should judge status %i as %s', (status, expected) => {
      // Act & Assert
      expect(isUnauthorized(new ApiError(status, 'error'))).toBe(expected);
    });
  });
});
