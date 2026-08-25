/**
 * 画面の初期化とイベント配線を行うエントリポイント。
 */

import * as api from "./api.js";
import * as ui from "./ui.js";

const authForm = document.getElementById("auth-form");
const registerButton = document.getElementById("register-button");
const logoutButton = document.getElementById("logout-button");
const messageForm = document.getElementById("message-form");
const messageText = document.getElementById("message-text");
const usernameInput = document.getElementById("username");
const passwordInput = document.getElementById("password");

/**
 * 例外を画面向けのメッセージへ変換する共通ハンドラ。
 * 401（セッション切れ）のときはログイン画面へ戻す。
 */
function handleError(error) {
  if (error instanceof api.ApiError && error.status === 401) {
    api.clearCsrfToken();
    ui.showLoggedOut();
    ui.showNotice("セッションが切れました。ログインし直してください。");
    return;
  }

  if (error instanceof api.ApiError) {
    ui.showNotice(error.message);
    return;
  }

  // ネットワーク断など、fetch自体が失敗した場合
  ui.showNotice("サーバーに接続できませんでした。通信環境を確認してください。");
}

/** 二重送信を防ぐため、非同期処理の間はフォームを無効化する。 */
async function withDisabled(form, action) {
  const fieldsets = Array.from(form.elements);
  fieldsets.forEach((element) => {
    element.disabled = true;
  });

  try {
    await action();
  } finally {
    fieldsets.forEach((element) => {
      element.disabled = false;
    });
  }
}

async function refreshMessages() {
  const messages = await api.fetchMessages();

  ui.renderMessages(messages, { onArchive: handleArchive });
}

async function handleArchive(messageId) {
  ui.clearNotice();

  try {
    await api.archiveMessage(messageId);
    await refreshMessages();
  } catch (error) {
    handleError(error);
  }
}

async function enterLoggedInState(user) {
  ui.showLoggedIn(user);
  await refreshMessages();
}

// --- イベント配線 ---

authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  ui.clearNotice();

  await withDisabled(authForm, async () => {
    try {
      const user = await api.login(usernameInput.value, passwordInput.value);

      passwordInput.value = "";

      await enterLoggedInState(user);
    } catch (error) {
      handleError(error);
    }
  });
});

registerButton.addEventListener("click", async () => {
  ui.clearNotice();

  // HTMLの検証属性（minlength等）はsubmit以外では自動実行されないため明示的に呼ぶ
  if (!authForm.reportValidity()) {
    return;
  }

  await withDisabled(authForm, async () => {
    try {
      // 登録APIはログイン状態にしないため、続けてログインする
      await api.registerUser(usernameInput.value, passwordInput.value);

      const user = await api.login(usernameInput.value, passwordInput.value);

      passwordInput.value = "";

      ui.showNotice("ユーザーを登録しました。", "success");

      await enterLoggedInState(user);
    } catch (error) {
      handleError(error);
    }
  });
});

logoutButton.addEventListener("click", async () => {
  ui.clearNotice();

  try {
    await api.logout();
    ui.showLoggedOut();
  } catch (error) {
    handleError(error);
  }
});

messageForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  ui.clearNotice();

  await withDisabled(messageForm, async () => {
    try {
      await api.createMessage(messageText.value);

      messageText.value = "";

      await refreshMessages();
    } catch (error) {
      handleError(error);
    }
  });
});

// --- 起動時のセッション復元 ---

/**
 * 再読み込み時に、Cookieが有効ならログイン状態を復元する。
 *
 * Session CookieはHttpOnlyでJSからは読めないため、/api/users/me を叩いて判定する。
 * CookieはブラウザにあるがCSRFトークンがsessionStorageに無い場合（別タブで開いた等）は、
 * 状態変更APIが必ず403になるためログイン画面へ戻す。
 */
async function bootstrap() {
  try {
    const user = await api.fetchCurrentUser();

    if (api.getCsrfToken() === null) {
      ui.showLoggedOut();
      ui.showNotice("操作を続けるにはログインし直してください。");
      return;
    }

    await enterLoggedInState(user);
  } catch (error) {
    if (error instanceof api.ApiError && error.status === 401) {
      // 未ログインは正常な状態なのでエラー表示しない
      api.clearCsrfToken();
      ui.showLoggedOut();
      return;
    }

    ui.showLoggedOut();
    handleError(error);
  }
}

bootstrap();
