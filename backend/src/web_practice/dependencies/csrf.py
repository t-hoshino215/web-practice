"""
FastAPIのDependencyとして利用する、CSRFトークン関連の依存関係を定義するモジュール。
"""

import secrets
from typing import Annotated

from fastapi import Cookie, Header, HTTPException, status

from web_practice.config import CSRF_COOKIE_NAME
from web_practice.dependencies import CurrentAuthSession
from web_practice.services import is_valid_csrf_token

# X-CSRF-Token HTTPヘッダーからCSRFトークンを取得する。
CsrfTokenHeader = Annotated[
    str | None,
    Header(alias="X-CSRF-Token"),
]

CsrfTokenCookie = Annotated[
    str | None,
    Cookie(alias=CSRF_COOKIE_NAME),
]


# 現在のSessionとリクエストのCSRFトークンが一致することを確認する。
# 不正または未指定の場合は403 Forbiddenを返す。
def require_csrf(
    auth_session: CurrentAuthSession,
    csrf_token: CsrfTokenHeader = None,
    csrf_cookie: CsrfTokenCookie = None,
) -> None:
    if csrf_token is None or csrf_cookie is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token required",
        )

    if not secrets.compare_digest(csrf_token, csrf_cookie) or not is_valid_csrf_token(
        csrf_token, auth_session.csrf_token_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )
