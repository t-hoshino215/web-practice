# Web Practice

Webサーバーの構築と公開の練習用レポジトリ

## Architecture

ソースコードの構造

```text
app/
├── main.py
├── database.py
├── dependencies.py
├── config.py
├── models/
│   ├── __init__.py
│   ├── message.py
│   ├── user.py
│   └── auth_session.py
├── schemas/
│   ├── __init__.py
│   ├── message.py
│   ├── user.py
│   └── auth.py
├── routers/
│   ├── __init__.py
│   ├── health.py
│   ├── messages.py
│   ├── users.py
│   └── auth.py
├── services/
│   ├── __init__.py
│   └── auth.py
├── alembic.ini
├── alembic/
├── pyproject.toml
└── Dockerfile
```

### Data Flow

```text
main.py
  ↓ FastAPIアプリを組み立てるだけ

routers/
  ↓ HTTP API

services/
  ↓ 認証などのアプリ内部処理

schemas/
  ↓ API入出力のPydanticモデル

models/
  ↓ SQLAlchemy DBモデル

database.py
  ↓ DB接続・Session・Base
```
