import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { buildMessage } from '../../tests/factories/models';
import { MessageList } from './MessageList';

describe('MessageList', () => {
  it('should render the empty state when there are no messages', () => {
    // Arrange & Act
    render(<MessageList messages={[]} disabled={false} onArchive={vi.fn()} />);

    // Assert
    expect(screen.getByText('メッセージはまだありません。')).toBeInTheDocument();
  });

  it('should render the raw text when the message contains HTML', () => {
    // Arrange
    const message = buildMessage({ text: '<img src=x onerror=alert(1)>' });

    // Act
    render(<MessageList messages={[message]} disabled={false} onArchive={vi.fn()} />);

    // Assert
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
  });

  it('should call onArchive with the message id when the archive button is clicked', async () => {
    // Arrange
    const message = buildMessage();
    const onArchive = vi.fn();
    render(<MessageList messages={[message]} disabled={false} onArchive={onArchive} />);

    // Act
    await userEvent.click(screen.getByRole('button', { name: 'アーカイブ' }));

    // Assert
    expect(onArchive).toHaveBeenCalledWith(message.id);
  });

  it('should not render the archive button when the message is already archived', () => {
    // Arrange
    const message = buildMessage({ is_archived: true });

    // Act
    render(<MessageList messages={[message]} disabled={false} onArchive={vi.fn()} />);

    // Assert
    expect(screen.queryByRole('button', { name: 'アーカイブ' })).not.toBeInTheDocument();
  });
});
