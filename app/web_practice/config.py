"""
共通で使用する設定値をまとめて管理するモジュール
"""

import os
from datetime import timedelta

# 環境変数からデータベースのURLを取得
DATABASE_URL = os.environ["DATABASE_URL"]

# セッション/Cookieの設定
SESSION_COOKIE_NAME = "session"
SESSION_LIFETIME = timedelta(days=7)

# CookieのSecure属性を有効にするかどうかを環境変数から取得する。(localhost環境ではfalse、本番(公開HTTPS)環境ではtrueにする想定)
COOKIE_SECURE = os.getenv(
    "COOKIE_SECURE",
    "false",
).lower() in {"1", "true", "yes", "on"}
