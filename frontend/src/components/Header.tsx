interface HeaderProps {
  readonly username: string | null;
  readonly disabled: boolean;
  readonly onLogout: () => void;
}

export function Header({ username, disabled, onLogout }: HeaderProps) {
  return (
    <header className="header">
      <h1 className="header__title">Web Practice</h1>

      {username !== null && (
        <div className="header__user">
          <span>{username}</span>
          <button type="button" className="button" disabled={disabled} onClick={onLogout}>
            ログアウト
          </button>
        </div>
      )}
    </header>
  );
}
