import type { Message } from '../api/schemas';

interface MessageItemProps {
  readonly message: Message;
  readonly disabled: boolean;
  readonly onArchive: (messageId: number) => void;
}

export function MessageItem({ message, disabled, onArchive }: MessageItemProps) {
  const className = message.is_archived ? 'message message--archived' : 'message';

  return (
    <li className={className}>
      {/* JSXが文字列を自動エスケープするため、HTMLとしては解釈されない */}
      <span className="message__text">{message.text}</span>

      <time className="message__time" dateTime={message.created_at}>
        {new Date(message.created_at).toLocaleString('ja-JP')}
      </time>

      {/* アーカイブ済みには再度アーカイブするボタンを出さない */}
      {!message.is_archived && (
        <button
          type="button"
          className="button"
          disabled={disabled}
          onClick={() => onArchive(message.id)}
        >
          アーカイブ
        </button>
      )}
    </li>
  );
}
