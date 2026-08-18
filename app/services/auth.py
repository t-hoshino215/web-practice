"""
認証関連のユーティリティ関数
ユーザー名、パスワード、セッショントークンに関する処理
"""

import hashlib
import secrets
from datetime import UTC, datetime

from pwdlib import PasswordHash

from config import SESSION_LIFETIME

# ----------------------------------------------
# パスワードハッシュの設定
# ----------------------------------------------

password_hasher = PasswordHash.recommended()

def hash_password(password: str) -> str:
    """
    平文パスワードからDB保存用のハッシュを生成する。
    """
    return password_hasher.hash(password)


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    """
    入力された平文パスワードがDBへ保存されているパスワードハッシュと一致するか検証する。
    """
    return password_hasher.verify(
        password,
        password_hash,
    )


# ----------------------------------------------
# セッショントークンの設定
# ----------------------------------------------

def generate_session_token() -> str:
    """
    推測困難なランダムなセッショントークンを生成する。
    この値そのものはCookieへ保存するが、DBには保存しない。
    """
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """
    生のセッショントークンから、DB検索・保存用のSHA-256ハッシュを生成する。
    """
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def create_session_expiration() -> datetime:
    """
    新しいログインセッションの有効期限をUTCで生成する。
    """
    return datetime.now(UTC) + SESSION_LIFETIME


# ----------------------------------------------
# ユーザー名の設定
# ----------------------------------------------

def normalize_username(username: str) -> str:
    """
    ユーザー名の表記揺れを防ぐため、前後の空白を除去して小文字へ統一する。
    """
    return username.strip().lower()
