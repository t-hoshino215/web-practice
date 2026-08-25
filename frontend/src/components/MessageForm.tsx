import { useState, type FormEvent } from 'react';

interface MessageFormProps {
  readonly disabled: boolean;
  /** 成功した場合にtrueを返す。失敗時に入力内容を失わせないため */
  readonly onSubmit: (text: string) => Promise<boolean>;
}

export function MessageForm({ disabled, onSubmit }: MessageFormProps) {
  const [text, setText] = useState('');

  async function submit(): Promise<void> {
    const succeeded = await onSubmit(text);

    if (succeeded) {
      setText('');
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();

    void submit();
  }

  return (
    <form className="form form--inline" onSubmit={handleSubmit}>
      <input
        className="form__input"
        id="message-text"
        name="text"
        type="text"
        required
        maxLength={255}
        placeholder="メッセージを入力"
        disabled={disabled}
        value={text}
        onChange={(event) => setText(event.target.value)}
      />
      <button className="button button--primary" type="submit" disabled={disabled}>
        追加
      </button>
    </form>
  );
}
