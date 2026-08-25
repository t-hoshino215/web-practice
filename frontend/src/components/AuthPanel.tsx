import { useState, type FormEvent, type MouseEvent } from 'react';

interface AuthPanelProps {
  readonly disabled: boolean;
  /** 成功した場合にtrueを返す。パスワード欄をクリアするかの判断に使う */
  readonly onLogin: (username: string, password: string) => Promise<boolean>;
  readonly onRegister: (username: string, password: string) => Promise<boolean>;
}

export function AuthPanel({ disabled, onLogin, onRegister }: AuthPanelProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  async function submit(action: (u: string, p: string) => Promise<boolean>): Promise<void> {
    const succeeded = await action(username, password);

    if (succeeded) {
      setPassword('');
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();

    void submit(onLogin);
  }

  function handleRegister(event: MouseEvent<HTMLButtonElement>): void {
    // type="button" ではブラウザの検証属性が自動実行されないため明示的に呼ぶ
    const form = event.currentTarget.form;

    if (form !== null && !form.reportValidity()) {
      return;
    }

    void submit(onRegister);
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <label className="form__label" htmlFor="username">
        ユーザー名
      </label>
      <input
        className="form__input"
        id="username"
        name="username"
        type="text"
        required
        minLength={3}
        maxLength={50}
        pattern="[A-Za-z0-9_-]+"
        autoComplete="username"
        disabled={disabled}
        value={username}
        onChange={(event) => setUsername(event.target.value)}
      />

      <label className="form__label" htmlFor="password">
        パスワード
      </label>
      <input
        className="form__input"
        id="password"
        name="password"
        type="password"
        required
        minLength={8}
        maxLength={128}
        autoComplete="current-password"
        disabled={disabled}
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />

      <div className="form__actions">
        <button className="button button--primary" type="submit" disabled={disabled}>
          ログイン
        </button>
        <button className="button" type="button" disabled={disabled} onClick={handleRegister}>
          新規登録
        </button>
      </div>
    </form>
  );
}
