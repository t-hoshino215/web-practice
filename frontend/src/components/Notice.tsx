export type NoticeKind = 'error' | 'success';

export interface NoticeState {
  readonly message: string;
  readonly kind: NoticeKind;
}

interface NoticeProps {
  readonly notice: NoticeState | null;
}

export function Notice({ notice }: NoticeProps) {
  if (notice === null) {
    return null;
  }

  return (
    // エラーはalertとして即座に読み上げ、成功通知はstatusとして控えめに伝える
    <p
      className="notice"
      data-kind={notice.kind}
      role={notice.kind === 'error' ? 'alert' : 'status'}
    >
      {notice.message}
    </p>
  );
}
