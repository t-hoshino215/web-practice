/**
 * DOM操作をまとめたモジュール。
 *
 * XSS対策の方針: ユーザー由来の文字列は必ず textContent で挿入し、innerHTML は使わない。
 * innerHTML を使うと、メッセージ本文に <script> や onerror 属性を仕込まれた場合に実行されてしまう。
 */

const elements = {
  notice: document.getElementById("notice"),
  headerUser: document.getElementById("header-user"),
  currentUsername: document.getElementById("current-username"),
  authPanel: document.getElementById("auth-panel"),
  messagesPanel: document.getElementById("messages-panel"),
  messageList: document.getElementById("message-list"),
  messageEmpty: document.getElementById("message-empty"),
};

// --- 通知 ---

export function showNotice(message, kind = "error") {
  elements.notice.textContent = message;
  elements.notice.dataset.kind = kind;
  elements.notice.hidden = false;
}

export function clearNotice() {
  elements.notice.textContent = "";
  elements.notice.hidden = true;
}

// --- 画面の切り替え ---

export function showLoggedIn(user) {
  elements.currentUsername.textContent = user.username;
  elements.headerUser.hidden = false;
  elements.authPanel.hidden = true;
  elements.messagesPanel.hidden = false;
}

export function showLoggedOut() {
  elements.currentUsername.textContent = "";
  elements.headerUser.hidden = true;
  elements.authPanel.hidden = false;
  elements.messagesPanel.hidden = true;
  elements.messageList.replaceChildren();
  elements.messageEmpty.hidden = true;
}

// --- メッセージ一覧 ---

/**
 * メッセージ一覧を描画する。
 * 受け取った配列は変更せず、DOM要素へ変換するだけに留める。
 */
export function renderMessages(messages, { onArchive }) {
  const items = messages.map((message) => buildMessageItem(message, onArchive));

  elements.messageList.replaceChildren(...items);
  elements.messageEmpty.hidden = messages.length > 0;
}

function buildMessageItem(message, onArchive) {
  const item = document.createElement("li");
  item.className = message.is_archived ? "message message--archived" : "message";

  const text = document.createElement("span");
  text.className = "message__text";
  // APIから返る文字列は必ずtextContentで挿入する
  text.textContent = message.text;

  const time = document.createElement("time");
  time.className = "message__time";
  time.dateTime = message.created_at;
  time.textContent = new Date(message.created_at).toLocaleString("ja-JP");

  item.append(text, time);

  // アーカイブ済みには再度アーカイブするボタンを出さない
  if (!message.is_archived) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button";
    button.textContent = "アーカイブ";
    button.addEventListener("click", () => onArchive(message.id));

    item.append(button);
  }

  return item;
}
