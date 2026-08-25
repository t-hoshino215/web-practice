import type { Message } from '../api/schemas';
import { MessageItem } from './MessageItem';

interface MessageListProps {
  readonly messages: readonly Message[];
  readonly disabled: boolean;
  readonly onArchive: (messageId: number) => void;
}

export function MessageList({ messages, disabled, onArchive }: MessageListProps) {
  if (messages.length === 0) {
    return <p className="message-list__empty">メッセージはまだありません。</p>;
  }

  return (
    <ul className="message-list">
      {messages.map((message) => (
        // keyは配列のindexではなくidを使う。並び替えや削除で表示がずれるのを防ぐ
        <MessageItem key={message.id} message={message} disabled={disabled} onArchive={onArchive} />
      ))}
    </ul>
  );
}
