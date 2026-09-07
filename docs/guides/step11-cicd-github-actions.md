# STEP 11: CI/CD（GitHub Actions）構築手順書

STEP 10 までで手作業になっている「テスト → イメージのビルド → サーバーへの反映 → Migration」を、GitHub Actions で自動化するまでの手順書。

GitHub Actions を初めて使う前提で、用語と仕組みの解説を挟みながら進める。

## このガイドのゴール

**mainブランチにマージしたら、テストが通ったコードだけが自動で本番（OCI VM）に反映される**状態を作る。

具体的には次の3つを自動化する。

1. **CI** — pushやPull Requestのたびに、バックエンド／フロントエンドのLint・型チェック・テスト・Dockerビルドを実行する
2. **イメージ配布** — mainにマージされたら、本番用のDockerイメージをビルドして GitHub Container Registry（GHCR）へpushする
3. **CD** — OCI VMへSSHして、イメージをpull → Alembic Migration → コンテナ差し替え、までを実行する

### 完成後のパイプライン

```text
[開発者]
  │ git push（feature ブランチ）
  ▼
[GitHub] ── Pull Request 作成
  │
  ├─▶ CI workflow（ci.yml）
  │     ├─ backend        : ruff / mypy / pytest
  │     ├─ frontend       : eslint / prettier / tsc / vitest
  │     └─ docker-build   : backend・frontendイメージがビルドできるか
  │
  │  すべて成功しないとマージできない（ブランチ保護ルール）
  ▼
[main へマージ]
  │
  ▼
[GitHub] ── Deploy workflow（deploy.yml）
  │
  ├─▶ build-and-push : 2つのイメージをビルドしてGHCRへpush
  │                     ghcr.io/<owner>/web-practice-backend:<commit sha>
  │                     ghcr.io/<owner>/web-practice-frontend:<commit sha>
  │
  └─▶ deploy         : SSHでOCI VMへ接続
        ├─ git fetch → デプロイ対象のコミットへ切り替え
        ├─ docker compose pull       … GHCRからイメージ取得
        ├─ alembic upgrade head      … DB Migration
        ├─ docker compose up -d      … コンテナ差し替え
        └─ /api/health のスモークテスト
```

STEP 10 までとの一番大きな違いは、**ビルドをサーバー上で行わなくなる**こと。OCI無料枠のVMはメモリが小さく `vite build` がOOMで落ちることがあるが、ビルドをGitHubの実行環境（2コア／16GBメモリ）に移せばこの問題が消える。サーバーは「出来上がったイメージを受け取って起動するだけ」になる。

### 前提

- STEP 10 までが完了し、`make up` でローカルの `http://localhost/` が動くこと
- OCI VM 上でも `docker compose` でアプリが動いていること（STEP 4・5・9・10 の公開手順が済んでいること）
- GitHubリポジトリが存在し、`git push` できること（このリポジトリは `github.com/<owner>/web-practice`）
- OCI VM にSSHでログインできること
- ローカルで次がすべて成功すること（CIで最初に落ちるのを防ぐため、先に確認しておく）

```bash
# backend/ で
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest --cov

# frontend/ で
pnpm install --frozen-lockfile
pnpm lint
pnpm format:check
pnpm typecheck
pnpm test
```

> ここで落ちる項目があれば、**先に直してから STEP 11 に進む**。CIは「ローカルで通ることをGitHubでも自動で確かめ続ける」仕組みであって、通らないものを通す仕組みではない。

### 全体の流れ

| # | 手順 | 変更対象 |
| --- | --- | --- |
| 11-1 | CI/CDとGitHub Actionsの基礎を押さえる | - |
| 11-2 | 最初のワークフローを動かす | `.github/workflows/hello.yml`（一時） |
| 11-3 | バックエンドのCIジョブを作る | `.github/workflows/ci.yml` |
| 11-4 | フロントエンドのCIジョブを追加する | `.github/workflows/ci.yml` |
| 11-5 | Dockerイメージのビルドを検証する | `.github/workflows/ci.yml` |
| 11-6 | PRベースの開発に切り替えてCIを必須にする | GitHubの設定 |
| 11-7 | イメージをGHCRへpushする | `.github/workflows/deploy.yml` |
| 11-8 | composeをイメージ参照に対応させる | `compose.yaml`, `Makefile` |
| 11-9 | デプロイ用の鍵とSecretsを用意する | OCI VM / GitHubの設定 |
| 11-10 | デプロイジョブを作る | `.github/workflows/deploy.yml` |
| 11-11 | デプロイを実行して確認する | - |
| 11-12 | 仕上げ | `.github/dependabot.yml`, `README.md` |
| 11-13 | ドキュメントを更新する | `README.md`, `CLAUDE.md`, `docs/` |

---

## 11-1. CI/CDとGitHub Actionsの基礎を押さえる

手を動かす前に、言葉の意味と仕組みを整理しておく。ここが曖昧なまま設定ファイルを書くと、エラーが出たときに何を疑えばいいか分からなくなる。

### CI（継続的インテグレーション）とは

**Continuous Integration** = 「変更を頻繁に本流へ統合し、そのたびに自動で検証する」こと。

STEP 10 までは、コードを変更したら自分で `pytest` や `pnpm test` を叩いていた。これには次の弱点がある。

| 手動実行の弱点 | CIでどう解決するか |
| --- | --- |
| 実行し忘れる。急いでいるときほど飛ばす | pushすれば必ず走る。忘れようがない |
| 「自分のPCでは通る」問題。ローカルにだけある設定やキャッシュに依存している | 毎回まっさらな環境で実行するので、依存の宣言漏れがすぐ露見する |
| 壊れたことに気づくのが遅れる | 数分以内にGitHub上で赤くなる |
| レビュー時に「テスト通しました？」と聞く必要がある | PR画面にチェック結果が出る |

CIの本質は**フィードバックを速く・確実にすること**であり、新しいテストを書くことではない。既にあるテストを、確実に・自動で回す土台をつくる。

### CD（継続的デリバリー／デプロイ）とは

**Continuous Delivery** = いつでもリリースできる成果物（ここではDockerイメージ）を常に用意しておくこと。
**Continuous Deployment** = そこからさらに進んで、検証を通った変更を自動で本番へ反映すること。

このSTEPでは、**mainへのマージをトリガーに自動デプロイする**（= Continuous Deployment）ところまでやる。ただし承認ステップ（Environment の required reviewers）を挟めるようにしておくので、「自動でイメージまで作る／人が承認したら本番へ出す」という Delivery 寄りの運用にも切り替えられる。

### GitHub Actionsの用語

GitHub Actions は GitHub に組み込まれた自動化基盤。次の階層になっている。

```text
Event（きっかけ）      … push / pull_request / 手動実行 など
  └─ Workflow（.github/workflows/*.yml … 1ファイル＝1ワークフロー）
       └─ Job（実行単位。1つのマシン上で動く。ジョブ同士は既定で並列）
            └─ Step（コマンド1行、または Action の呼び出し）
                 ├─ run:  … シェルコマンドを実行する
                 └─ uses: … 公開された Action（部品）を使う
```

| 用語 | 意味 | このプロジェクトでの例 |
| --- | --- | --- |
| Workflow | 自動化のまとまり。`.github/workflows/` 配下のYAML | `ci.yml`, `deploy.yml` |
| Event（トリガー） | ワークフローを起動するきっかけ | `push`, `pull_request`, `workflow_dispatch`（手動） |
| Job | 1台の仮想マシン上で順に実行されるステップの束 | `backend`, `frontend`, `deploy` |
| Runner | ジョブを実行するマシン。GitHubのホスト型を使う | `ubuntu-latest` |
| Step | ジョブ内の1手順 | `uv run pytest` |
| Action | 再利用可能な部品。`uses:` で呼ぶ | `actions/checkout`, `docker/build-push-action` |
| Secret | ログに出ない秘密の値 | `SSH_KEY`, `SSH_HOST` |
| Artifact | ジョブが残すファイル。ジョブ間の受け渡しやダウンロードに使う | （今回は未使用） |
| Cache | 依存パッケージなどを次回実行へ持ち越す仕組み | uvキャッシュ・pnpmストア |
| Matrix | 同じジョブを変数違いで並列実行する仕組み | backend／frontendの2イメージビルド |

覚えておくと理解が早い性質。

- **ジョブごとにまっさらな仮想マシンが立ち上がる。** ジョブAで `pip install` してもジョブBには残らない。ファイルを渡したければ Artifact か Cache を使う
- **ジョブは既定で並列。** 順序を付けたいときだけ `needs:` で依存を宣言する
- **ステップは上から順で、1つ失敗した時点でそのジョブは失敗して止まる**
- **リポジトリのコードは自動では置かれない。** `actions/checkout` を最初に実行して初めてソースがrunner上に現れる

### ワークフローファイルの構造

最小のワークフローに注釈を付けるとこうなる。

```yaml
name: CI                       # GitHubのActionsタブに表示される名前

on:                            # ① いつ動かすか（Event）
  pull_request:                #   PRの作成・更新時
  push:
    branches:
      - main                   #   mainへのpush時

jobs:                          # ② 何をするか
  backend:                     #   ジョブID（英数字・ハイフン。他ジョブから参照する名前）
    name: Backend              #   画面上の表示名。ブランチ保護の「必須チェック名」にもなる
    runs-on: ubuntu-latest     #   どのマシンで動かすか
    steps:
      - name: Check out        #   ③ ステップ
        uses: actions/checkout@v5   #   公開Actionを使う（@v5 はバージョン）
      - name: Say hello
        run: echo "hello"      #   シェルコマンドを実行する
```

YAMLでよくつまずく点。

- **インデントはスペースのみ。** タブは構文エラーになる
- **`-` はリストの要素。** `steps:` の各ステップ、`branches:` の各ブランチはリスト
- **`on:` はYAMLでは真偽値の `true` と解釈される場合がある。** GitHub Actionsは特別扱いするので問題ないが、エディタの警告が出ても無視してよい
- **`${{ ... }}` は式（expression）。** GitHubが実行前に値を埋め込む。`${{ github.sha }}` や `${{ secrets.SSH_HOST }}` など

### 料金と実行時間の上限

| 項目 | 内容 |
| --- | --- |
| publicリポジトリ | GitHubホスト型runnerの実行時間は**無料**（標準runner） |
| privateリポジトリ | Freeプランで月2,000分まで無料。Linux runnerは実測分がそのまま消費される |
| 1ジョブの上限 | 6時間（超えると強制終了） |
| 1ワークフローの上限 | 35日 |
| キャッシュ | リポジトリあたり10GB。溢れると古いものから削除される |

このプロジェクトのCIは1回あたり数分程度。とはいえ、無駄な実行を減らす設定（`concurrency` による古い実行のキャンセル）は 11-3 で入れる。

> 使用量は `Settings` → `Billing and licensing` → `Usage` で確認できる。

---

## 11-2. 最初のワークフローを動かす

いきなり本番用のワークフローを書くと、失敗したときに「YAMLが悪いのか、コマンドが悪いのか、権限が悪いのか」が切り分けられない。まず**確実に成功する最小のワークフロー**を1本動かして、仕組みと画面の見方を掴む。

### ワークフローの置き場所

GitHub Actions は `.github/workflows/` 配下の `.yml` / `.yaml` を自動で認識する。**この場所以外に置いても動かない。**

```bash
mkdir -p .github/workflows
```

### Hello Actions

```bash
cat > .github/workflows/hello.yml <<'EOF'
name: Hello

# 手動実行だけのワークフロー。Actionsタブから「Run workflow」で起動する
on:
  workflow_dispatch:

jobs:
  hello:
    name: Hello
    runs-on: ubuntu-latest
    steps:
      - name: Check out the repository
        uses: actions/checkout@v5

      - name: Show environment
        run: |
          echo "ブランチ: ${{ github.ref_name }}"
          echo "コミット: ${{ github.sha }}"
          echo "起動した人: ${{ github.actor }}"
          uname -a
          node -v
          python3 -V
          docker -v

      - name: Show repository files
        run: ls -la
```

`workflow_dispatch` は「Actionsタブのボタンから手動で実行する」トリガー。pushで勝手に走らないので、練習に向いている。

コミットしてpushする。

```bash
git add .github/workflows/hello.yml
git commit -m "ci: add a hello workflow to try GitHub Actions"
git push
```

### 実行を確認する

1. GitHubのリポジトリページ → **Actions** タブを開く
2. 左サイドバーに `Hello` が現れる。選択して **Run workflow** → ブランチを選んで実行
3. 実行中の行をクリック → ジョブ `Hello` をクリック → 各ステップの `▶` を開くとログが読める

見ておきたいポイント。

| 見る場所 | 分かること |
| --- | --- |
| ステップ「Set up job」 | runnerのOSイメージ、事前インストール済みソフト一覧へのリンク |
| ステップ「Check out the repository」 | `actions/checkout` がリポジトリを取得している |
| ステップ「Show environment」 | Node・Python・Dockerが**最初から入っている**こと |
| ステップ「Show repository files」 | checkout前は空、checkout後にファイルがある |
| 右上の所要時間 | 課金対象の実行時間 |

`ubuntu-latest` には Node・Python・Docker・git などが最初から入っている。ただしバージョンはGitHub都合で変わるので、**プロジェクトが必要とするバージョンは自分で明示的にセットアップする**（次のステップでやる）。

### 動作を確認したら削除する

役目は終わったので消す。ワークフローファイルを削除すれば、そのワークフローは消える。

```bash
rm .github/workflows/hello.yml
git add -A
git commit -m "ci: remove the hello workflow"
git push
```

---

## 11-3. バックエンドのCIジョブを作る

ここから本番用のCIを作る。まずバックエンドだけ。

### `.github/workflows/ci.yml`

```yaml
name: CI

# PRのたび、およびmainへのpushのたびに実行する
on:
  pull_request:
  push:
    branches:
      - main

# 同じブランチで新しいpushがあったら、実行中の古いCIをキャンセルする（実行時間の節約）
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

# ワークフロー全体の既定権限を「読み取りのみ」に絞る
permissions:
  contents: read

jobs:
  backend:
    name: Backend
    runs-on: ubuntu-latest
    timeout-minutes: 15
    # このジョブのすべての run: を backend/ で実行する
    defaults:
      run:
        working-directory: backend
    steps:
      - name: Check out the repository
        uses: actions/checkout@v5

      - name: Set up uv
        uses: astral-sh/setup-uv@v6
        with:
          version: "0.12.5"
          enable-cache: true
          cache-dependency-glob: backend/uv.lock

      - name: Install dependencies
        run: uv sync --locked

      - name: Lint (ruff check)
        run: uv run ruff check .

      - name: Format check (ruff format)
        run: uv run ruff format --check .

      - name: Type check (mypy)
        run: uv run mypy src

      - name: Test (pytest)
        run: uv run pytest --cov
```

### 各ステップの意味（backend）

| ステップ | 何をしているか | 補足 |
| --- | --- | --- |
| `actions/checkout@v5` | リポジトリをrunnerへ取得する | これが無いとソースが存在しない |
| `astral-sh/setup-uv@v6` | uv本体をインストールし、キャッシュを有効にする | `version` はローカル／Dockerfileと同じ `0.12.5` に揃える |
| `uv sync --locked` | `uv.lock` の通りに依存を入れる | Pythonも `.python-version`（3.14）に従ってuvが用意する |
| `uv run ruff check .` | Lint | ローカルと同じコマンド |
| `uv run ruff format --check .` | フォーマット崩れの検出 | `--check` は書き換えずに差分があれば失敗する |
| `uv run mypy src` | 型チェック | |
| `uv run pytest --cov` | テストとカバレッジ | テストはSQLite in-memoryを使うのでDBサービス不要 |

いくつか意図的な選択がある。

- **`--locked` を付ける。** ロックファイルと `pyproject.toml` がずれていたら**依存を勝手に更新せずに失敗する**。CIでロックファイルの更新漏れを検出できる
- **`ruff format` は `--check` にする。** CIがコードを書き換えるのは避ける。直すのは開発者の手元
- **PostgreSQLサービスを立てていない。** `backend/tests/conftest.py` がテスト用に `DATABASE_URL` をSQLiteのin-memoryへ差し替えているため。PostgreSQL固有の挙動を検証したくなったら、`services:` でPostgreSQLコンテナを足す（→ 「既知の制約」）
- **`timeout-minutes` を付ける。** ハングしたジョブが6時間回り続けるのを防ぐ

### ローカルとの対応

CIが「ローカルと同じことをしている」と分かっていると、失敗したときに手元で再現できる。

| CIのステップ | 手元で叩く同じコマンド（`backend/` で実行） |
| --- | --- |
| Install dependencies | `uv sync --locked` |
| Lint | `uv run ruff check .` |
| Format check | `uv run ruff format --check .`（直すなら `uv run ruff format .`） |
| Type check | `uv run mypy src` |
| Test | `uv run pytest --cov` |

pushして、Actionsタブで `CI` が緑になることを確認する。

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add backend CI workflow"
git push
```

### 失敗したときの読み方

赤くなったら、次の順で見る。

1. **どのジョブが赤いか**（backend / frontend / docker-build）
2. **どのステップが赤いか**（Lint なのか Test なのか）— ステップ名を分けているのはこのため
3. **ログの末尾**。ログ画面右上の検索窓で `Error` や `FAILED` を検索すると早い
4. 手元で同じコマンドを実行して再現する

「手元では通るのにCIだけ落ちる」場合の典型は次の3つ。

| 症状 | 原因 |
| --- | --- |
| `uv sync --locked` で失敗 | `pyproject.toml` を変更したのに `uv.lock` を更新・コミットしていない |
| インポートエラー | ローカルにだけ入っているパッケージに依存している（依存宣言の漏れ） |
| テストだけ落ちる | テストが実行順や既存データ、ローカルの環境変数に依存している |

---

## 11-4. フロントエンドのCIジョブを追加する

`ci.yml` の `jobs:` に `frontend` を足す。`backend` と同じ階層（インデント）に書く。

### frontendジョブを追加する

```yaml
  frontend:
    name: Frontend
    runs-on: ubuntu-latest
    timeout-minutes: 15
    defaults:
      run:
        working-directory: frontend
    steps:
      - name: Check out the repository
        uses: actions/checkout@v5

      # package.json の packageManager フィールドを読んで pnpm を用意する
      - name: Set up pnpm
        uses: pnpm/action-setup@v4
        with:
          package_json_file: frontend/package.json

      - name: Set up Node.js
        uses: actions/setup-node@v5
        with:
          node-version: 24
          cache: pnpm
          cache-dependency-path: frontend/pnpm-lock.yaml

      - name: Install dependencies
        run: pnpm install --frozen-lockfile

      - name: Lint (ESLint)
        run: pnpm lint

      - name: Format check (Prettier)
        run: pnpm format:check

      - name: Type check (tsc)
        run: pnpm typecheck

      - name: Test (Vitest)
        run: pnpm test
```

### 各ステップの意味（frontend）

| ステップ | 何をしているか | 補足 |
| --- | --- | --- |
| `pnpm/action-setup@v4` | pnpmを用意する | `package_json_file` の指定が要る。このリポジトリは**ルートに `package.json` が無く** `frontend/` にあるため |
| `actions/setup-node@v5` | Node 24 を用意し、pnpmストアをキャッシュする | `cache: pnpm` は**pnpmが先に入っていること**が前提。だから順番が pnpm → Node |
| `pnpm install --frozen-lockfile` | ロックファイル通りに依存を入れる | ずれていれば失敗する（`uv sync --locked` と同じ思想） |
| `pnpm lint` / `format:check` / `typecheck` / `test` | `frontend/package.json` の scripts をそのまま呼ぶ | CI専用のコマンドを新設しないのがポイント |

**CIにコマンドを直書きせず、`package.json` の scripts を呼ぶ**ようにしておくと、ローカルとCIの実行内容が自動的に一致し続ける。`pnpm test` は `vitest run`（ウォッチしない1回実行）になっている点も確認しておく。ウォッチモードのままだとCIが終わらない。

### ジョブは並列で走る

`backend` と `frontend` の間に `needs:` を書いていないので、この2つは**同時に**別々のマシンで走る。合計時間は「遅いほうの時間」で済む。

```text
        ┌── backend  （約 1〜2分）──┐
push ──┤                            ├── 両方成功でCI成功
        └── frontend （約 1〜2分）──┘
```

pushして、Actionsタブに `Backend` と `Frontend` の2つが並んで実行されることを確認する。

---

## 11-5. Dockerイメージのビルドを検証する

Lintとテストが通っても、**Dockerfileが壊れていればデプロイできない**。「マージした後にビルドが失敗する」を防ぐため、PRの段階でイメージがビルドできるかを確かめる。

### docker-buildジョブを追加する

```yaml
  docker-build:
    name: Docker build
    runs-on: ubuntu-latest
    timeout-minutes: 30
    # テストが通ってから実行する（無駄なビルドを避ける）
    needs:
      - backend
      - frontend
    strategy:
      # 同じ手順を、変数を変えて並列に実行する
      matrix:
        include:
          - name: backend
            context: ./backend
          - name: frontend
            context: ./frontend
    steps:
      - name: Check out the repository
        uses: actions/checkout@v5

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build image (${{ matrix.name }})
        uses: docker/build-push-action@v6
        with:
          context: ${{ matrix.context }}
          target: runtime
          push: false
          load: false
          cache-from: type=gha,scope=${{ matrix.name }}
          cache-to: type=gha,mode=max,scope=${{ matrix.name }}
```

### なぜCIでビルドするのか

| 検出できること | 例 |
| --- | --- |
| Dockerfileの構文・COPYパスの誤り | `COPY src/ ./src/` の対象を移動したのに直していない |
| `.dockerignore` の漏れ | ビルドに必要なファイルを除外してしまった |
| ロックファイルとイメージのずれ | `pnpm install --frozen-lockfile` がイメージ内で失敗する |
| 型エラー | `frontend/Dockerfile` の `pnpm build` は `pnpm typecheck` を含む |

`target: runtime` は多段ビルドの最終ステージ名。`backend/Dockerfile`・`frontend/Dockerfile` のどちらも `AS runtime` が最終ステージなので、`compose.yaml` の指定と揃えている。

`push: false` なのでレジストリには何も送らない。**ビルドが通るかどうかだけ**を見るジョブ。

### キャッシュの仕組み

`cache-from` / `cache-to` の `type=gha` は、GitHub Actions のキャッシュ領域にDockerのレイヤーキャッシュを保存する指定。

- `mode=max` … 中間レイヤーも含めて保存する。次回のビルドが大幅に速くなる
- `scope=...` … キャッシュの名前空間。backendとfrontendで分けないと互いに上書きし合う
- キャッシュはリポジトリ全体で10GBまで。溢れると古いものから消える（壊れるわけではなく、単にビルドが遅くなる）

> `frontend/Dockerfile` の `RUN --mount=type=cache,id=pnpm,...` というBuildKitのキャッシュマウントは、GHAキャッシュには保存されない（ビルドマシンローカルの仕組みのため）。レイヤーキャッシュは効くので、`package.json` と `pnpm-lock.yaml` が変わらなければ `pnpm install` のレイヤーごと再利用される。

### CIの完成形

ここまでで `.github/workflows/ci.yml` は次の形になる。

```yaml
name: CI

on:
  pull_request:
  push:
    branches:
      - main

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  backend:
    name: Backend
    runs-on: ubuntu-latest
    timeout-minutes: 15
    defaults:
      run:
        working-directory: backend
    steps:
      - name: Check out the repository
        uses: actions/checkout@v5

      - name: Set up uv
        uses: astral-sh/setup-uv@v6
        with:
          version: "0.12.5"
          enable-cache: true
          cache-dependency-glob: backend/uv.lock

      - name: Install dependencies
        run: uv sync --locked

      - name: Lint (ruff check)
        run: uv run ruff check .

      - name: Format check (ruff format)
        run: uv run ruff format --check .

      - name: Type check (mypy)
        run: uv run mypy src

      - name: Test (pytest)
        run: uv run pytest --cov

  frontend:
    name: Frontend
    runs-on: ubuntu-latest
    timeout-minutes: 15
    defaults:
      run:
        working-directory: frontend
    steps:
      - name: Check out the repository
        uses: actions/checkout@v5

      - name: Set up pnpm
        uses: pnpm/action-setup@v4
        with:
          package_json_file: frontend/package.json

      - name: Set up Node.js
        uses: actions/setup-node@v5
        with:
          node-version: 24
          cache: pnpm
          cache-dependency-path: frontend/pnpm-lock.yaml

      - name: Install dependencies
        run: pnpm install --frozen-lockfile

      - name: Lint (ESLint)
        run: pnpm lint

      - name: Format check (Prettier)
        run: pnpm format:check

      - name: Type check (tsc)
        run: pnpm typecheck

      - name: Test (Vitest)
        run: pnpm test

  docker-build:
    name: Docker build
    runs-on: ubuntu-latest
    timeout-minutes: 30
    needs:
      - backend
      - frontend
    strategy:
      matrix:
        include:
          - name: backend
            context: ./backend
          - name: frontend
            context: ./frontend
    steps:
      - name: Check out the repository
        uses: actions/checkout@v5

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build image (${{ matrix.name }})
        uses: docker/build-push-action@v6
        with:
          context: ${{ matrix.context }}
          target: runtime
          push: false
          load: false
          cache-from: type=gha,scope=${{ matrix.name }}
          cache-to: type=gha,mode=max,scope=${{ matrix.name }}
```

> **Actionのバージョンについて。** `@v5` のようなメジャーバージョンタグを指定すると、互換性のある更新は自動で取り込まれる。実際に使うときは各Actionのリポジトリ（Marketplace）で最新のメジャーバージョンを確認すること。より厳密にやるならコミットSHAで固定する（`actions/checkout@<sha>`）。サプライチェーン攻撃対策としてはSHA固定が最も安全で、更新は 11-12 のDependabotに任せられる。

---

## 11-6. PRベースの開発に切り替えてCIを必須にする

CIを作っても、**mainへ直接pushし続けるなら意味が半減する**。「壊れたコードがmainに入る前に止める」ためには、変更をPull Request（PR）経由にして、CIの成功をマージ条件にする必要がある。

### ブランチを切って進める

これまでのようにmainへ直接コミットするのをやめ、次の流れにする。

```bash
# 1. 作業用ブランチを切る
git switch -c ci/add-github-actions

# 2. 変更をコミットしてpush
git add .github/workflows/ci.yml
git commit -m "ci: add CI workflow for backend, frontend and docker build"
git push -u origin ci/add-github-actions

# 3. Pull Request を作る（GitHub CLI がある場合）
gh pr create --fill

# gh が無ければ、pushしたときに表示されるURLをブラウザで開く
```

PR画面の下部に、CIの各ジョブの結果が並ぶ。

```text
✓ CI / Backend                   Successful in 1m 20s
✓ CI / Frontend                  Successful in 1m 05s
✓ CI / Docker build (backend)    Successful in 2m 10s
✓ CI / Docker build (frontend)   Successful in 3m 42s
```

すべて緑になったらマージする。

```bash
gh pr merge --squash --delete-branch
```

### ブランチ保護ルールを設定する

CIが赤くてもマージできてしまっては保護にならない。GitHubの設定で、**CIの成功をマージの必須条件**にする。

1. リポジトリの **Settings** → **Rules** → **Rulesets** → **New ruleset** → **New branch ruleset**
2. `Ruleset Name` に `protect-main` などを入力し、`Enforcement status` を **Active** にする
3. `Target branches` → **Add target** → **Include default branch**（= main）
4. `Rules` で次にチェックを入れる

| ルール | 効果 |
| --- | --- |
| **Require a pull request before merging** | mainへの直接pushを禁止し、必ずPRを経由させる |
| **Require status checks to pass** | 指定したCIチェックが成功しないとマージできない |
| **Block force pushes** | `git push --force` による履歴の破壊を防ぐ |

続けて `Require status checks to pass` を開き、**Add checks** で次の4つを追加する。

```text
Backend
Frontend
Docker build (backend)
Docker build (frontend)
```

さらに `Require branches to be up to date before merging` を有効にすると、「mainの最新を取り込んだ状態でCIが通ったこと」を要求できる（より安全だが、PRが多いと再実行が増える）。

> 旧UIの **Settings** → **Branches** → **Add branch protection rule** でもほぼ同じことができる。GitHubは Rulesets への移行を進めているので、新規なら Rulesets を使う。

### 必須チェックの名前

必須チェックの候補として出てくる名前は、**ジョブの `name:` の値**（matrixの場合は `name (matrix値)`）。一度もそのチェックが実行されていないと候補に出てこないので、**先に1回PRを作ってCIを走らせてから**設定するのが確実。

注意点。

- ジョブの `name:` を変えると必須チェックの名前も変わる。ルールが古い名前のままだと「永遠に来ないチェック」を待ち続けてマージできなくなる。名前を変えたらルールも更新する
- 同じ理由で、`on:` に `paths:` フィルタを付けてジョブをスキップさせると、必須チェックが未実行のまま待ち状態になる。パスによる実行制御が必要になったら `dorny/paths-filter` などで**ジョブは必ず実行し、中の重い処理だけスキップする**形にする

これ以降、STEP 11 の残りの作業も同じようにブランチ → PR → マージで進める。

---

## 11-7. イメージをGHCRへpushする

CIができたので、次はデプロイ用の成果物（Dockerイメージ）を作って配る。

### GHCRとは

**GitHub Container Registry**（`ghcr.io`）は、GitHubが提供するDockerイメージの保管場所。Docker Hub と同じ用途だが、GitHubリポジトリと権限が連動し、Actionsから追加の認証情報なしで使える点が便利。

このプロジェクトでは2つのイメージを作る。

| イメージ | 中身 | ビルド元 |
| --- | --- | --- |
| `ghcr.io/<owner>/web-practice-backend` | FastAPI + 依存 | `backend/Dockerfile`（`runtime` ステージ） |
| `ghcr.io/<owner>/web-practice-frontend` | Caddy + Viteのビルド成果物 | `frontend/Dockerfile`（`runtime` ステージ） |

`<owner>` はGitHubのユーザー名または組織名。**GHCRのイメージ名は小文字のみ**なので、ユーザー名に大文字が含まれる場合は小文字に変換して指定する。

### `deploy.yml` のビルドジョブ

新しいワークフローファイル `.github/workflows/deploy.yml` を作る。まずはビルドとpushだけ。

```yaml
name: Deploy

on:
  # mainへのpush（＝PRのマージ）で動く
  push:
    branches:
      - main
  # 手動実行も可能にしておく（初回の動作確認やリトライに使う）
  workflow_dispatch:

# デプロイは同時に走らせない。実行中なら次の実行を待たせる（キャンセルはしない）
concurrency:
  group: deploy-production
  cancel-in-progress: false

permissions:
  contents: read

jobs:
  build-and-push:
    name: Build and push
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions:
      contents: read
      packages: write        # GHCRへpushするために必要
    strategy:
      matrix:
        include:
          - name: backend
            context: ./backend
            image: web-practice-backend
          - name: frontend
            context: ./frontend
            image: web-practice-frontend
    steps:
      - name: Check out the repository
        uses: actions/checkout@v5

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push (${{ matrix.name }})
        uses: docker/build-push-action@v6
        with:
          context: ${{ matrix.context }}
          target: runtime
          push: true
          tags: |
            ghcr.io/${{ github.repository_owner }}/${{ matrix.image }}:${{ github.sha }}
            ghcr.io/${{ github.repository_owner }}/${{ matrix.image }}:latest
          labels: |
            org.opencontainers.image.source=${{ github.server_url }}/${{ github.repository }}
            org.opencontainers.image.revision=${{ github.sha }}
          cache-from: type=gha,scope=${{ matrix.name }}
          cache-to: type=gha,mode=max,scope=${{ matrix.name }}
```

### タグ設計

1つのイメージに2つのタグを付けている。役割が違う。

| タグ | 例 | 役割 |
| --- | --- | --- |
| コミットSHA | `:8f3a1c9...` | **デプロイで実際に使う。** 内容が一意に決まり、後から同じものを取り直せる |
| `latest` | `:latest` | 人が「最新はどれ？」と見るための目印。デプロイには使わない |

**なぜデプロイに `latest` を使わないのか。**

`latest` は同じ名前のまま中身が変わる。サーバー上の `latest` がいつビルドされたものか分からなくなり、「どのコミットが動いているか」を追えなくなる。障害時の切り分けもロールバックもできない。

コミットSHAで指定すれば、

- サーバーで動いているイメージとリポジトリのコミットが1対1で対応する
- ロールバックは「前のSHAのタグで起動し直す」だけで済む
- デプロイのたびにイメージ参照が変わるので、`docker compose up -d` が**確実にコンテナを作り直す**

### GITHUB_TOKENと権限

`${{ secrets.GITHUB_TOKEN }}` は、**ワークフロー実行のたびにGitHubが自動発行する一時トークン**。自分で作って登録する必要はなく、ジョブが終われば無効になる。

権限は `permissions:` で明示する。

```yaml
permissions:
  contents: read      # リポジトリの読み取り（checkoutに必要）
  packages: write     # GHCRへのpush
```

ワークフロー冒頭では `contents: read` だけにしておき、必要なジョブでだけ `packages: write` を足す。これが**最小権限の原則**。トークンが漏れたときの被害範囲が小さくなる。

> `labels` に `org.opencontainers.image.source` を付けると、GHCRのパッケージページがリポジトリと紐付き、説明や権限の継承が効くようになる。

### pushされたイメージを確認する

PRをマージ（またはActionsタブから `Deploy` を手動実行）すると `build-and-push` が走る。

確認場所はGitHubのユーザー（または組織）ページ → **Packages** タブ。`web-practice-backend` と `web-practice-frontend` が出てくる。

パッケージの公開範囲は既定で **private**。このあとサーバーからpullするので、どちらかを選ぶ。

| 方式 | 手順 | 判断 |
| --- | --- | --- |
| A. パッケージをpublicにする | パッケージページ → `Package settings` → `Change visibility` → Public | 誰でもpullできる。中身が公開されてよい場合のみ |
| B. privateのまま、デプロイ時にサーバーからログインする | デプロイジョブが渡す `GITHUB_TOKEN` でVM側が `docker login` する | **採用**。追加の秘密情報が不要で、権限も実行中だけ有効 |

このガイドは **B** で進める。具体的な手順は 11-10 に含まれる。

---

## 11-8. composeをイメージ参照に対応させる

サーバー側の役割が「ビルドする」から「pullして起動する」に変わるので、`compose.yaml` にイメージ名を持たせる。

### `compose.yaml` の変更

`backend` と `caddy` の各サービスに `image:` を追加する。

```yaml
  backend:
    # 環境変数が無ければローカルビルド用の名前を使う。
    # CI/CDからは ghcr.io の完全なイメージ名（タグ＝コミットSHA）を渡す
    image: ${BACKEND_IMAGE:-web-practice-backend:local}
    build:
      context: ./backend
      target: runtime
    environment:
      DATABASE_URL: >-
        postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      COOKIE_SECURE: ${COOKIE_SECURE:-false}
    expose:
      - "8000"
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped
```

```yaml
  caddy:
    # フロントエンドのビルド成果物を同梱したCaddyイメージ（frontend/Dockerfile）
    image: ${FRONTEND_IMAGE:-web-practice-caddy:local}
    build:
      context: ./frontend
      target: runtime
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - backend
    restart: unless-stopped
```

`${VAR:-default}` は「`VAR` が未設定または空なら `default` を使う」という Compose の記法。

### ローカルの挙動は変わらない

`BACKEND_IMAGE` / `FRONTEND_IMAGE` を設定しなければ、これまで通り `build:` からローカルビルドされ、イメージに `web-practice-backend:local` という名前が付くだけ。`make up` も `make build-front` もそのまま動く。

一方サーバー側では、環境変数を与えることで**同じ `compose.yaml` のままpull運用に切り替わる**。

```bash
# サーバー側での実行イメージ
export BACKEND_IMAGE="ghcr.io/<owner>/web-practice-backend:<sha>"
export FRONTEND_IMAGE="ghcr.io/<owner>/web-practice-frontend:<sha>"

docker compose --env-file ./backend/.env pull backend caddy
docker compose --env-file ./backend/.env up -d backend caddy
```

> Compose の値の優先順位は「シェルの環境変数 > `--env-file` で指定したファイル > `.env`」。`export` した値が最優先で効く。
> なお `--env-file` を指定すると既定の `.env` は読まれなくなる。このプロジェクトは元から `--env-file ./backend/.env` で運用しているので、そのまま踏襲する。

**`image:` と `build:` を両方書いた場合、`docker compose up -d` はローカルにイメージがあればビルドせずそれを使う。** サーバーでは `--build` を付けないこと（付けるとGHCRから取ったイメージをローカルビルドで上書きしてしまう）。

### Makefileにデプロイ用ターゲットを足す（任意）

サーバーで手動確認・ロールバックするときのために、`Makefile` に追加しておくと楽になる。

```makefile
# GHCRのイメージを取得して起動する（サーバー側での手動デプロイ・ロールバック用）
# 使い方: make deploy TAG=<commit sha>
GHCR_OWNER ?= <owner>
TAG ?= latest
DEPLOY_IMAGES := \
 BACKEND_IMAGE=ghcr.io/$(GHCR_OWNER)/web-practice-backend:$(TAG) \
 FRONTEND_IMAGE=ghcr.io/$(GHCR_OWNER)/web-practice-frontend:$(TAG)

deploy:
 $(DEPLOY_IMAGES) docker compose --env-file ./backend/.env pull backend caddy
 $(DEPLOY_IMAGES) docker compose --env-file ./backend/.env up -d backend caddy
 docker compose --env-file ./backend/.env ps
```

`.PHONY` の行にも `deploy` を追加しておく。

---

## 11-9. デプロイ用の鍵とSecretsを用意する

GitHub ActionsからOCI VMへSSH接続するための準備をする。

### デプロイ専用のSSH鍵を作る

**普段使っている個人の鍵は使わない。** GitHubに預ける鍵は「デプロイ専用」に新しく作り、漏れたときに差し替えられるようにする。

ローカルで実行する。

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy@web-practice" -f ~/.ssh/web_practice_deploy -N ""
```

| オプション | 意味 |
| --- | --- |
| `-t ed25519` | 鍵の種類。現在の推奨 |
| `-C` | コメント。何の鍵か後で分かるようにする |
| `-f` | 出力先。`web_practice_deploy`（秘密鍵）と `web_practice_deploy.pub`（公開鍵）ができる |
| `-N ""` | パスフレーズ無し。自動実行では入力できないため |

### 公開鍵をOCI VMに登録する

公開鍵の中身を表示し、その1行をVMの `~/.ssh/authorized_keys` の末尾に追記する。

```bash
# ローカルで公開鍵を表示
cat ~/.ssh/web_practice_deploy.pub
```

VM上で `~/.ssh/authorized_keys` を編集して貼り付ける。パーミッションは `600`、`~/.ssh` は `700` にしておく。

登録できたら、ローカルから新しい鍵で接続を確認する。

```bash
ssh -i ~/.ssh/web_practice_deploy <ユーザー名>@<VMのIP> "hostname && docker -v"
```

> **VM側のDocker権限。** デプロイユーザーが `sudo` 無しで `docker` を実行できる必要がある。できない場合は `sudo usermod -aG docker $USER` を実行し、一度ログインし直す。

### ホスト鍵のフィンガープリントを控える

接続先が本当に自分のVMかを検証するために、ホスト鍵のフィンガープリントを取得する。これを設定しないと「初回接続の警告を無視して繋ぐ」＝なりすましを検出できない状態になる。

```bash
ssh-keyscan -t ed25519 <VMのIP> 2>/dev/null | ssh-keygen -lf -
```

出力例。

```text
256 SHA256:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx <VMのIP> (ED25519)
```

`SHA256:` から始まる部分を控える。

### GitHubにSecretsを登録する

リポジトリの **Settings** → **Secrets and variables** → **Actions** → **New repository secret**。

| Secret名 | 値 | 備考 |
| --- | --- | --- |
| `SSH_HOST` | OCI VMのパブリックIP（またはホスト名） | |
| `SSH_USER` | VMのログインユーザー名（例: `ubuntu`） | |
| `SSH_KEY` | 秘密鍵 `~/.ssh/web_practice_deploy` の**中身すべて** | `-----BEGIN ...` から `-----END ...` の行まで、改行込みで丸ごと |
| `SSH_FINGERPRINT` | 上で控えた `SHA256:...` | |
| `DEPLOY_PATH` | VM上のリポジトリのパス（例: `/home/ubuntu/web-practice`） | |

**Secretsについて知っておくこと。**

- 一度保存すると**画面上でも読み出せない**（更新・削除のみ）。手元にも控えておく
- ログに出力されそうになると自動で `***` にマスクされる。ただしBase64化したり分割したりすると素通りするので、**そもそもログに出さない**
- フォークからのPull Requestで実行されるワークフローには渡されない（外部の人がPRで秘密を抜けないようにする仕組み）
- 似た機能に **Variables** があるが、そちらはマスクされない。秘密でない値（ドメイン名など）向け

### Environmentを作る

デプロイ先を「環境」として登録すると、承認フローやデプロイ履歴が使えるようになる。

1. **Settings** → **Environments** → **New environment** → 名前を `production`
2. 必要なら **Required reviewers** に自分を追加する（デプロイ前に承認ボタンを押す運用になる）
3. **Deployment branches** を `Selected branches` にして `main` のみ許可する

Environmentを設定しておくメリット。

| 機能 | 効果 |
| --- | --- |
| Required reviewers | 承認するまでデプロイジョブが待機する。自動デプロイの安全弁 |
| Deployment branches | main以外のブランチからのデプロイを拒否する |
| Environment secrets | 環境ごとに違う秘密を持てる（将来 staging を足すときに効く） |
| デプロイ履歴 | リポジトリのトップページに「Deployments」として履歴が出る |

> まず承認ありで運用し、慣れたら Required reviewers を外して完全自動にする、という進め方がおすすめ。

---

## 11-10. デプロイジョブを作る

`deploy.yml` に、OCI VMへ反映するジョブを追加する。

### deployジョブを追加する

`build-and-push` と同じ階層に追記する。

```yaml
  deploy:
    name: Deploy to production
    runs-on: ubuntu-latest
    timeout-minutes: 15
    # イメージのpushが終わってから実行する
    needs: build-and-push
    # Environmentを指定すると、承認・デプロイ履歴・環境別Secretが使えるようになる
    environment:
      name: production
      url: https://taph-lab.com
    permissions:
      contents: read
      packages: read       # VM側がGHCRからpullするためのトークンに必要
    steps:
      - name: Deploy over SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.SSH_HOST }}
          username: ${{ secrets.SSH_USER }}
          key: ${{ secrets.SSH_KEY }}
          fingerprint: ${{ secrets.SSH_FINGERPRINT }}
          # ここに列挙した環境変数だけがリモートへ引き渡される
          envs: DEPLOY_PATH,GHCR_USER,GHCR_TOKEN,IMAGE_OWNER,IMAGE_TAG
          script_stop: true
          script: |
            set -euo pipefail

            cd "$DEPLOY_PATH"

            # デプロイ対象のコミットへ揃える（compose.yaml と Caddyfile をイメージと一致させる）
            git fetch --prune origin
            git switch --detach "$IMAGE_TAG"

            # GHCRのprivateパッケージをpullするためのログイン
            echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin

            export BACKEND_IMAGE="ghcr.io/$IMAGE_OWNER/web-practice-backend:$IMAGE_TAG"
            export FRONTEND_IMAGE="ghcr.io/$IMAGE_OWNER/web-practice-frontend:$IMAGE_TAG"

            # 1) 新しいイメージを取得する
            docker compose --env-file ./backend/.env pull backend caddy

            # 2) DB Migration を適用する（新しいイメージのalembicを使う）
            docker compose --env-file ./backend/.env run --rm backend alembic upgrade head

            # 3) コンテナを新しいイメージで作り直す
            docker compose --env-file ./backend/.env up -d backend caddy

            docker compose --env-file ./backend/.env ps

            # 後始末
            docker logout ghcr.io
            docker image prune --force
        env:
          DEPLOY_PATH: ${{ secrets.DEPLOY_PATH }}
          GHCR_USER: ${{ github.actor }}
          GHCR_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          IMAGE_OWNER: ${{ github.repository_owner }}
          IMAGE_TAG: ${{ github.sha }}

      - name: Smoke test
        run: |
          set -euo pipefail
          for i in $(seq 1 10); do
            code=$(curl -fsS -o /dev/null -w '%{http_code}' https://taph-lab.com/api/health) && break || true
            echo "retry $i ..."
            sleep 5
          done
          echo "status: ${code:-none}"
          test "${code:-}" = "200"
```

### デプロイスクリプトの流れ

| # | コマンド | 目的 |
| --- | --- | --- |
| 1 | `git fetch` + `git switch --detach "$IMAGE_TAG"` | `compose.yaml` と `Caddyfile` を、イメージと同じコミットの内容に揃える |
| 2 | `docker login ghcr.io` | privateパッケージをpullするための認証 |
| 3 | `docker compose pull backend caddy` | 新しいイメージを取得する。ここで失敗すれば**まだ何も切り替わっていない**ので安全 |
| 4 | `alembic upgrade head` | DBスキーマを更新する |
| 5 | `docker compose up -d backend caddy` | イメージ参照が変わっているので、両コンテナが作り直される |
| 6 | `docker logout` / `docker image prune` | トークンを残さない。古いイメージでディスクを埋めない |

**`git switch --detach` について。**
コミットSHAを直接指すため、HEADがブランチから外れた「detached HEAD」状態になる。デプロイ用のチェックアウトとしては正しい状態（デプロイした内容が一意に定まる）だが、SSHで手動作業するときに戸惑いやすい。ブランチに戻したいときは次を実行する。

```bash
git switch main
```

**`docker image prune --force` について。**
タグの付いていない古いイメージ（dangling image）だけを消す。動作中のコンテナが使っているイメージは消えない。OCI無料枠VMはディスクも小さいので、毎回入れておくと安心。ディスク使用量は `docker system df` で確認できる。

**スモークテストについて。**
デプロイ後に `/api/health` が200を返すかを確認する。コンテナ起動には数秒かかるのでリトライしている。ここで失敗すればワークフローが赤くなり、「デプロイは走ったが動いていない」ことに気づける。

### Migrationの位置と後方互換性

`alembic upgrade head` を**コンテナ差し替えの前**に置いている。この順序には意味と制約がある。

```text
時刻 →
  [旧コード稼働中] ──────┬─────────────▶ [新コード稼働]
                          │
                    Migration適用
                    （この間、旧コードが新しいスキーマを触る）
```

つまり**数秒〜数十秒のあいだ、旧コードが新スキーマのDBにアクセスする**。そのため、Migrationは**旧コードでも壊れない変更**である必要がある。

| 安全な変更 | 危険な変更 |
| --- | --- |
| NULL許容カラムの追加 | NOT NULLカラムの追加（旧コードのINSERTが失敗する） |
| 新しいテーブルの追加 | カラムのリネーム（旧コードが古い名前を参照して失敗する） |
| インデックスの追加 | カラム・テーブルの削除 |

破壊的な変更が必要なときは、**Expand and Contract（拡張と収縮）**という定石を使う。

1. **Expand**: 新カラムを追加する（旧コードは無視できる）→ デプロイ
2. **Migrate**: 新コードが両方を書き、データを移行する → デプロイ
3. **Contract**: 旧カラムを削除する → デプロイ

1回のデプロイに詰め込まず、3回に分ける。このプロジェクトの規模なら、まずは「NOT NULLを足したくなったら、いったんNULL許容で入れる」だけ意識しておけば十分。

> どうしても危険な変更を一度に入れる場合は、`workflow_dispatch` の手動デプロイに切り替え、メンテナンス時間を取って実施する。

### deploy.ymlの完成形

```yaml
name: Deploy

on:
  push:
    branches:
      - main
  workflow_dispatch:

concurrency:
  group: deploy-production
  cancel-in-progress: false

permissions:
  contents: read

jobs:
  build-and-push:
    name: Build and push
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions:
      contents: read
      packages: write
    strategy:
      matrix:
        include:
          - name: backend
            context: ./backend
            image: web-practice-backend
          - name: frontend
            context: ./frontend
            image: web-practice-frontend
    steps:
      - name: Check out the repository
        uses: actions/checkout@v5

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push (${{ matrix.name }})
        uses: docker/build-push-action@v6
        with:
          context: ${{ matrix.context }}
          target: runtime
          push: true
          tags: |
            ghcr.io/${{ github.repository_owner }}/${{ matrix.image }}:${{ github.sha }}
            ghcr.io/${{ github.repository_owner }}/${{ matrix.image }}:latest
          labels: |
            org.opencontainers.image.source=${{ github.server_url }}/${{ github.repository }}
            org.opencontainers.image.revision=${{ github.sha }}
          cache-from: type=gha,scope=${{ matrix.name }}
          cache-to: type=gha,mode=max,scope=${{ matrix.name }}

  deploy:
    name: Deploy to production
    runs-on: ubuntu-latest
    timeout-minutes: 15
    needs: build-and-push
    environment:
      name: production
      url: https://taph-lab.com
    permissions:
      contents: read
      packages: read
    steps:
      - name: Deploy over SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.SSH_HOST }}
          username: ${{ secrets.SSH_USER }}
          key: ${{ secrets.SSH_KEY }}
          fingerprint: ${{ secrets.SSH_FINGERPRINT }}
          envs: DEPLOY_PATH,GHCR_USER,GHCR_TOKEN,IMAGE_OWNER,IMAGE_TAG
          script_stop: true
          script: |
            set -euo pipefail

            cd "$DEPLOY_PATH"

            git fetch --prune origin
            git switch --detach "$IMAGE_TAG"

            echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin

            export BACKEND_IMAGE="ghcr.io/$IMAGE_OWNER/web-practice-backend:$IMAGE_TAG"
            export FRONTEND_IMAGE="ghcr.io/$IMAGE_OWNER/web-practice-frontend:$IMAGE_TAG"

            docker compose --env-file ./backend/.env pull backend caddy
            docker compose --env-file ./backend/.env run --rm backend alembic upgrade head
            docker compose --env-file ./backend/.env up -d backend caddy
            docker compose --env-file ./backend/.env ps

            docker logout ghcr.io
            docker image prune --force
        env:
          DEPLOY_PATH: ${{ secrets.DEPLOY_PATH }}
          GHCR_USER: ${{ github.actor }}
          GHCR_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          IMAGE_OWNER: ${{ github.repository_owner }}
          IMAGE_TAG: ${{ github.sha }}

      - name: Smoke test
        run: |
          set -euo pipefail
          for i in $(seq 1 10); do
            code=$(curl -fsS -o /dev/null -w '%{http_code}' https://taph-lab.com/api/health) && break || true
            echo "retry $i ..."
            sleep 5
          done
          echo "status: ${code:-none}"
          test "${code:-}" = "200"
```

---

## 11-11. デプロイを実行して確認する

### サーバー側を先に整えておく

初回だけ、VM側の状態を確認する。

```bash
# VM上で実行
cd <DEPLOY_PATHに設定したパス>

# リポジトリが最新のリモートを見ているか
git remote -v
git fetch --prune origin

# backend/.env が存在し、COOKIE_SECURE=true になっているか
ls -l backend/.env

# 現在のコンテナ状態
docker compose --env-file ./backend/.env ps
```

`compose.yaml` の `image:` 追加（11-8）を含むコミットがVM側に取り込まれている必要がある。デプロイジョブが `git switch --detach` するので自動的に揃うが、初回は手動で `git pull` して確認しておくと切り分けが楽。

### 初回は手動実行で試す

いきなりmainへのマージで走らせるより、**Actionsタブからの手動実行**で試すほうが安全。

1. GitHub → **Actions** → 左サイドバーの **Deploy** を選択
2. **Run workflow** → ブランチ `main` を選んで実行

`workflow_dispatch` を `on:` に入れておいたのはこのため。

### 承認して実行する

Environmentに Required reviewers を設定した場合、`deploy` ジョブは待機状態になる。

1. 実行中のワークフロー画面に **Review deployments** ボタンが出る
2. `production` にチェックを入れて **Approve and deploy**

承認するとSSHが始まる。ログには次のような流れが出る。

```text
======CMD======
set -euo pipefail
cd "$DEPLOY_PATH"
...
======END======
out: Pulling backend  ... done
out: Pulling caddy    ... done
out: INFO  [alembic.runtime.migration] Running upgrade ... -> ...
out: Container web-practice-backend-1  Recreated
out: Container web-practice-caddy-1    Recreated
```

### サーバー側の確認

```bash
# 動いているイメージがGHCRのSHAタグになっているか
docker compose --env-file ./backend/.env ps --format 'table {{.Service}}\t{{.Image}}\t{{.Status}}'

# 適用済みのMigration
docker compose --env-file ./backend/.env run --rm backend alembic current

# ログ
docker compose --env-file ./backend/.env logs --tail 50 backend
docker compose --env-file ./backend/.env logs --tail 50 caddy
```

ブラウザとcurlでの最終確認。

```bash
curl -I https://taph-lab.com/
curl -i https://taph-lab.com/api/health
curl -i https://taph-lab.com/api/db-health
```

より詳しい疎通確認は [docs/healthcheck.md](../healthcheck.md) の「② 公開サーバー向け」を使う。

### ロールバック手順

デプロイ後に問題が見つかったら、**1つ前のコミットSHAのイメージで起動し直す**。

```bash
# VM上で実行。<前のSHA> はGitHubのコミット履歴やPackagesのタグから取得する
cd <DEPLOY_PATH>

PREV=<前のコミットSHA>

export BACKEND_IMAGE="ghcr.io/<owner>/web-practice-backend:$PREV"
export FRONTEND_IMAGE="ghcr.io/<owner>/web-practice-frontend:$PREV"

git switch --detach "$PREV"
docker compose --env-file ./backend/.env pull backend caddy
docker compose --env-file ./backend/.env up -d backend caddy
```

11-8 の `make deploy` を用意していれば、次の1行で済む。

```bash
make deploy TAG=<前のコミットSHA>
```

**DBのロールバックは自動では戻らない。** Migrationを戻す必要がある場合は明示的に実行する。

```bash
docker compose --env-file ./backend/.env run --rm backend alembic downgrade -1
```

ただし `downgrade` はデータを失う可能性がある（追加したカラムを消せば、そこに入ったデータは消える）。だからこそ 11-10 の「後方互換な変更にしておく」が効いてくる。**コードだけロールバックすれば復旧できる**状態を保つのが基本方針。

その後、GitHub側では問題のコミットを `git revert` してPRを出し、通常のフローで直す。

---

## 11-12. 仕上げ

### ステータスバッジ

`README.md` の先頭付近にCIの状態バッジを置くと、リポジトリを開いた瞬間に健全性が分かる。

```markdown
[![CI](https://github.com/<owner>/web-practice/actions/workflows/ci.yml/badge.svg)](https://github.com/<owner>/web-practice/actions/workflows/ci.yml)
[![Deploy](https://github.com/<owner>/web-practice/actions/workflows/deploy.yml/badge.svg)](https://github.com/<owner>/web-practice/actions/workflows/deploy.yml)
```

### Dependabotでアクションと依存を更新する

`.github/dependabot.yml` を置くと、GitHubが依存の更新PRを自動で作ってくれる。CIが揃った今なら、**更新PRの安全性をCIが検証してくれる**ので導入する価値が高い。

```yaml
version: 2
updates:
  # GitHub Actions のバージョン更新
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly

  # Python（uv.lock）
  - package-ecosystem: uv
    directory: /backend
    schedule:
      interval: weekly

  # Node（pnpm-lock.yaml）
  - package-ecosystem: npm
    directory: /frontend
    schedule:
      interval: weekly

  # Dockerfile のベースイメージ
  - package-ecosystem: docker
    directories:
      - /backend
      - /frontend
    schedule:
      interval: weekly
```

最初は更新PRが大量に来るので、`open-pull-requests-limit: 3` を各エントリに足して絞ってもよい。

### 権限を最小にする

セキュリティの観点で確認しておくポイント。

| 項目 | 設定 | 場所 |
| --- | --- | --- |
| ワークフローの既定権限 | `contents: read` のみ | 各ワークフローの `permissions:` |
| GITHUB_TOKENの組織既定 | `Read repository contents permission` | Settings → Actions → General |
| フォークPRからの実行 | 承認を必須にする | Settings → Actions → General → Fork pull request workflows |
| Actionの実行許可 | 信頼できる作成者のものに限定する | Settings → Actions → General → Actions permissions |
| サードパーティAction | メジャータグではなくコミットSHAで固定する | 各 `uses:` |

`pull_request_target` というトリガーは、フォークからのPRでもSecretsが使える強力なもの。**便利だが危険**なので、このプロジェクトでは使わない。

### 実行時間を短くする

CIが遅いと、そのうち結果を待たなくなる。効いてくる順に。

| 施策 | 効果 |
| --- | --- |
| `concurrency` で古い実行をキャンセル（導入済み） | 連続pushの無駄をなくす |
| 依存キャッシュ（導入済み） | `uv sync` / `pnpm install` が数秒で終わる |
| Dockerレイヤーキャッシュ（導入済み） | イメージビルドが大幅に短縮される |
| ジョブの並列化（導入済み） | 合計時間が「一番遅いジョブ」に収まる |
| `docker-build` を `needs` で後置（導入済み） | テストが落ちるPRで重いビルドを走らせない |

### Markdownのlintを追加する（任意）

このリポジトリには `.markdownlint-cli2.jsonc` があるので、ドキュメントのlintもCIに載せられる。

```yaml
  docs:
    name: Docs
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - name: Check out the repository
        uses: actions/checkout@v5

      - name: Lint Markdown
        uses: DavidAnson/markdownlint-cli2-action@v20
        with:
          globs: "**/*.md"
```

ドキュメントを重視しているプロジェクトなので相性がよい。必須チェックに含めるかどうかは好みで決める。

---

## 11-13. ドキュメントを更新する

### `README.md` の更新

- 冒頭にCI／Deployのバッジを追加する
- `Tech Stack` に「CI/CD: GitHub Actions」「レジストリ: GitHub Container Registry」を追加する
- `Repository layout` に `.github/workflows/` を追加する
- `STEP` の表で、STEP 11 を「予定」から「完了」へ移し、この手順書へリンクする
- `Getting Started` に「デプロイはmainへのマージで自動実行される」旨と、手動デプロイ／ロールバックの手順を追記する

```text
├── .github/
│   ├── workflows/
│   │   ├── ci.yml               # Lint・型チェック・テスト・イメージビルド検証
│   │   └── deploy.yml           # GHCRへpush → OCI VMへデプロイ
│   └── dependabot.yml           # 依存とActionの更新PR
```

### `CLAUDE.md` の更新

- `Complete learning steps` の STEP 11 を完了として扱う
- `Workflow` に「mainへの直接pushは禁止。変更はブランチ → PR → CI通過 → マージ」を追記する
- `Tech Stack` に CI/CD の項目を追記する

### `docs/dev-commandlist.md` の更新

サーバー側の手動デプロイとロールバックのコマンドを追記しておくと、緊急時に探さずに済む。

```bash
# 手動デプロイ（VM上）
make deploy TAG=<commit sha>

# ロールバック（VM上）
make deploy TAG=<前のcommit sha>

# 適用済みMigrationの確認
docker compose --env-file ./backend/.env run --rm backend alembic current
```

### 後片付け

- `.github/workflows/hello.yml` が残っていないか確認する（11-2で削除済みのはず）
- 使わなくなった手順（サーバー上での `docker compose build`）が手順書に残っていないか確認する
- GHCRの古いイメージを整理する（→ 「既知の制約」）

---

## トラブルシューティング

### CIが動かない・失敗する

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| ワークフローが一度も起動しない | ファイルの場所・拡張子が違う | `.github/workflows/*.yml` であること。`.github/workflow/` は誤り |
| YAMLのエラーで即失敗 | インデントにタブが混在 | スペースのみに揃える。エディタでタブを可視化する |
| `uv sync --locked` が失敗 | `pyproject.toml` を変えたのに `uv.lock` が古い | ローカルで `uv sync` して `uv.lock` をコミットする |
| `pnpm install --frozen-lockfile` が失敗 | `package.json` と `pnpm-lock.yaml` がずれている | ローカルで `pnpm install` して `pnpm-lock.yaml` をコミットする |
| `pnpm: command not found` | `setup-node` を先に置いてしまった | `pnpm/action-setup` → `actions/setup-node` の順にする |
| `packageManager` が見つからない | ルートに `package.json` が無い | `pnpm/action-setup` に `package_json_file: frontend/package.json` を指定する |
| テストがCIだけ落ちる | ローカルの環境変数・DB・実行順に依存している | 失敗ログを読み、テストの前提を切り離す |
| ジョブが延々終わらない | ウォッチモードのコマンドを実行している | `vitest` ではなく `vitest run`（`pnpm test`）を使う |

### イメージのpushで失敗する

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| `denied: permission_denied` | ジョブに `packages: write` が無い | `build-and-push` ジョブの `permissions:` を確認する |
| `invalid reference format` | イメージ名に大文字が含まれている | オーナー名・イメージ名を小文字にする |
| `unauthorized` | `docker/login-action` の前にpushしている | ステップの順序を確認する |
| ビルドが極端に遅い | キャッシュが効いていない | `cache-from` / `cache-to` の `scope` がイメージごとに分かれているか確認する |

### デプロイで失敗する

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| `ssh: handshake failed` | `SSH_KEY` の内容が不完全 | `-----BEGIN`／`-----END` 行を含めて全文を貼り直す |
| `fingerprint mismatch` | `SSH_FINGERPRINT` が違う／VMを再作成した | `ssh-keyscan` で取り直して更新する |
| 接続がタイムアウトする | OCIのSecurity List／VM内のfirewallで22番が閉じている | Ingress Rule と `iptables`／`ufw` を確認する |
| `permission denied (publickey)` | 公開鍵が `authorized_keys` に入っていない／権限が緩い | `~/.ssh` は700、`authorized_keys` は600 |
| `docker: permission denied` | デプロイユーザーがdockerグループにいない | `sudo usermod -aG docker $USER` 後に再ログイン |
| `Error response from daemon: ... denied` | GHCRのprivateパッケージにログインできていない | `packages: read` 権限と `docker login` のステップを確認する |
| `pathspec '<sha>' did not match` | VM側で `git fetch` できていない | リモートURLと、VMからGitHubへの到達性を確認する |
| Migrationで失敗 | 既存データと制約が衝突している | ログを読み、Migrationを後方互換な形に書き直す |
| スモークテストだけ失敗 | 起動に時間がかかっている／アプリが起動していない | VMで `docker compose logs backend` を確認する |
| `no space left on device` | VMのディスクが埋まっている | `docker system df` → `docker system prune -a --volumes` は**volumeを消すので使わない**。`docker image prune -a` で古いイメージを削除する |

### 権限・設定まわり

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| PRがマージできない（チェック待ち） | 必須チェック名とジョブ名が一致していない | ブランチ保護ルールのチェック名を実際のジョブ名に合わせる |
| デプロイジョブが待機したまま | Environmentの承認待ち | `Review deployments` から承認する |
| Secretsが空で渡る | 名前のタイプミス、Environment secretとrepository secretの取り違え | 定義した場所とスコープを確認する |
| ログに秘密が出てしまった | `echo` してしまった | 該当のSecret（SSH鍵など）を**すぐ再発行して差し替える**。ログ削除だけでは不十分 |

---

## 既知の制約

STEP 11 の構成が抱えている割り切りを明示しておく。STEP 12 以降で扱う課題でもある。

### デプロイ中に短いダウンタイムが出る

`docker compose up -d` はコンテナを停止してから作り直すため、数秒間リクエストが失敗する。無停止にするには、複数インスタンスを立てて順次入れ替える（ローリングアップデート）か、Blue/Greenの仕組みが要る。個人開発の練習用としては許容範囲。

### CIとデプロイは並行して走る

`ci.yml` と `deploy.yml` はどちらも「mainへのpush」で起動するため、**CIの完了を待たずにデプロイが始まる**。これが許されるのは、11-6 のブランチ保護によって**mainにはCIを通ったコードしか入らない**からである。

保護を外したり管理者権限で直接pushしたりすると、この前提が崩れる。Rulesetsで「Do not allow bypassing the above settings」を有効にしておくと確実になる。

厳密に「CI成功後にだけデプロイする」を実現したい場合は、`deploy.yml` のトリガーを `workflow_run` に変える方法がある。ただし `workflow_run` は、実行されるワークフロー定義が常に既定ブランチのものになる・`github.sha` が対象コミットとずれる（`github.event.workflow_run.head_sha` を使う必要がある）といった癖があるので、慣れてから採用する。

### Migrationのロールバックは自動化していない

コードは前のSHAへ戻せるが、DBスキーマは自動では戻らない。`alembic downgrade` はデータ損失を伴い得るため、意図的に手動操作にしている。運用の基本は「**後方互換なMigrationを書き、コードだけ戻せば復旧できる状態を保つ**」こと。

### GHCRのイメージは溜まり続ける

コミットごとにタグを作るので、放置するとバージョンが増え続ける。GitHubのパッケージ設定で保持ポリシーを設定するか、`actions/delete-package-versions` などで古いバージョンを定期削除する。無料枠の範囲であればしばらくは問題にならない。

### SSHポートを世界に開けている

GitHubホスト型runnerのIPは広範囲で固定できないため、実質「どこからでも22番に接続を試せる」状態になっている。鍵認証のみ（`PasswordAuthentication no`）にしていれば実害は起きにくいが、より安全にするなら次の選択肢がある。

| 方式 | 内容 |
| --- | --- |
| GitHubのIPレンジに限定 | `https://api.github.com/meta` の `actions` レンジを許可する。数が多く、変更もあるため運用負荷は高い |
| セルフホストrunner | VM自身をrunnerにしてSSHを不要にする。runnerの安全な運用が別途必要 |
| Tailscale / Cloudflare Tunnel | 一時的に閉域網へ参加してから接続する。公開ポートを増やさずに済む |

### PostgreSQL固有の挙動をCIで検証していない

テストはSQLiteのin-memoryで動く。速くて手軽な反面、PostgreSQL固有の型・制約・SQLの差は検出できない。必要になったら、CIに `services:` でPostgreSQLを立て、`DATABASE_URL` を渡す統合テストジョブを追加する。

```yaml
    services:
      postgres:
        image: postgres:18-alpine
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd "pg_isready -U postgres"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
        ports:
          - 5432:5432
```

---

## STEP 12（運用基盤）への引き継ぎ

STEP 11 で「変更を安全に届ける」仕組みができた。STEP 12 は「届けたあと、動き続けさせる」仕組みを扱う。

| 項目 | STEP 11（現在） | STEP 12（運用基盤） |
| --- | --- | --- |
| DBのバックアップ | 無し。VMが壊れたらデータが消える | `pg_dump` の定期取得とリストア手順の確立 |
| ログ | `docker compose logs` を手で見る | ローテーション・集約・保持期間の設計 |
| ヘルスチェック | デプロイ直後のスモークテストのみ | 常時監視と失敗時の通知 |
| 障害検知 | ブラウザで気づく | 監視サービス／自前のチェックによる自動検知 |
| 通知 | 無し（Actionsのメールのみ） | デプロイ結果・障害のSlack等への通知 |

STEP 11 の成果物のうち、STEP 12 でそのまま拡張できるもの。

- **スモークテストのステップ** — 監視の最小形。チェック項目を増やせばそのまま死活監視の土台になる
- **`deploy.yml` の構造** — 通知ステップ（`if: failure()`）を足すだけで、失敗時のアラートを送れる
- **バックアップの自動化** — `schedule:` トリガーのワークフローから、VM上の `pg_dump` を定期実行できる

```yaml
# STEP 12 で使う形のイメージ
on:
  schedule:
    - cron: "0 18 * * *"   # UTC。JSTの毎日3時
```

---

## 導入記録

この手順書に沿った導入記録。

| # | 手順 | ステータス | コミット |
| --- | --- | --- | --- |
| 11-1 | CI/CDとGitHub Actionsの基礎を押さえる | 完了 | - |
| 11-2 | 最初のワークフローを動かす | 完了 | a42f023232e2c8f3ecf5cbb8b6278d9c5e1fac3a / 9f984fd253b8c91d64424ef0f6a0b4cf0c59b07b |
| 11-3 | バックエンドのCIジョブを作る | 完了 | e604de7653ec5025b0b98140d679313d64e41c97 / fefb0be2e3a7d04f6f0b7fddce8eeda5006aecd7 |
| 11-4 | フロントエンドのCIジョブを追加する | 完了 | 01f85887e28479ad27d8135fcfd69f5a46f0f9ee / 53dbb2dc08b78312d830734effcb7493904405b4 |
| 11-5 | Dockerイメージのビルドを検証する | 完了 | e38431d6a39bf99ce7f6f84fa486bd3a91a76411 |
| 11-6 | PRベースの開発に切り替えてCIを必須にする | 完了 | 879d891207c29249663e695e3bbe219634871307 |
| 11-7 | イメージをGHCRへpushする | 完了 | 45aa358d0e63fbfbc45d72b0321d3fa7f01edd3d |
| 11-8 | composeをイメージ参照に対応させる | 完了 | f1b341e349c7ece108a58fc1e233bf6a0dbe2eaa |
| 11-9 | デプロイ用の鍵とSecretsを用意する | 完了 | - |
| 11-10 | デプロイジョブを作る | 完了 | f1b341e349c7ece108a58fc1e233bf6a0dbe2eaa / 7fdfe49c82573feef904f0382d41e6b968adbabe |
| 11-11 | デプロイを実行して確認する | 完了 | cf16c0d059f50bedbc6ec21a68b76a3afb046048 / aff59251b7098aa5bfbbf7d02f9d8b2d9a81bbba |
| 11-12 | 仕上げ | 完了 (一部見送り) | - |
| 11-13 | ドキュメントを更新する | 完了 | - |

追記:

- 11-2〜11-5 は `main` への直接pushで進め、11-6 以降はPR運用（PR #1〜#6）に切り替えた。
- 11-6のブランチ保護ルール、11-9のSSH鍵・Secrets・Environment、11-12の権限設定は、いずれもGitHub／OCI側のGUI設定のためコミットは残らない。
- 11-10で `appleboy/ssh-action@v1` の `script_stop: true` が廃止済みオプションだったため削除した（`7fdfe49`）。
- 11-11でSSHのホスト鍵検証に失敗したため、`ssh-keyscan` でRunnerから見えるfingerprintを表示する診断ステップを一時的に追加し、原因の特定後に削除した（`cf16c0d` → `aff5925`）。
- 11-12の「Markdownのlintを追加する（任意）」は**見送った**。理由: `markdownlint-cli2` を `**/*.md` に適用すると11ファイル・48件の違反（`docs/plans/` のMD029、`docs/logs/` のMD013、`.claude/` 配下）が出るため、先に既存ドキュメントの整理が必要。整理後に `docs` ジョブを追加する。
- 11-12の「サードパーティActionをコミットSHAで固定する」は**未実施**。手順書のYAMLとの対応を読みやすく保つことを優先し、バージョンタグのまま Dependabot の更新に任せる。
- 11-13で `docs/dev-commandlist.md` に `## Deploy / Rollback` を追加し、手動デプロイ・ロールバック・適用済みMigrationの確認コマンドをまとめた。

---

## 付録: 変更からデプロイまでのgit / gh操作

STEP 11 の完成後、コードを変更するときの実際の手順。11-6 のブランチ保護により **`main` への直接pushはできない**（`git push origin main` は `GH006: Protected branch update failed` で拒否される）。すべての変更をブランチ → PR → CI → マージの順に流す。

```text
git switch -c ...  →  git commit  →  git push  →  gh pr create  →  [CI]  →  gh pr merge  →  [CI + Deploy]  →  本番反映
                                                      ↑                        ↑
                                              ここで初めてCIが動く      マージ＝mainへのpushでデプロイが動く
```

### 操作とCI/CDの対応早見表

| 操作 | 起動するワークフロー | 何が起こるか |
| --- | --- | --- |
| `git switch -c <branch>` / `git commit` | なし | ローカルのみ。GitHubには何も伝わらない |
| `git push origin <branch>`（PR未作成） | なし | `ci.yml` の `on:` は `pull_request` と `push: main` だけなので走らない |
| `gh pr create` | CI | `Backend` / `Frontend` / `Docker build (backend)` / `Docker build (frontend)` |
| PRブランチへの追加push | CI（再実行） | `concurrency` により、実行中の古いCIはキャンセルされる |
| `gh pr merge`（＝ `main` へのpush） | CI と Deploy | Deploy: GHCRへpush → SSH → `alembic upgrade head` → `up -d` → スモークテスト |
| Actionsタブの **Run workflow** | Deploy | `workflow_dispatch`。`main` の現在のHEADで手動デプロイ |
| Dependabotの週次PR | CI | 依存・Actionの更新PR。マージすればDeployも走る |

CIとDeployは**どちらも「mainへのpush」で起動するため並行して走る**。詳しくは「既知の制約」の「CIとデプロイは並行して走る」を参照。

### 0. 事前準備（初回のみ）

```bash
# GitHub CLI の認証状態を確認し、未認証ならログインする
gh auth status || gh auth login
```

### 1. mainを最新にしてブランチを切る

```bash
git switch main
git pull --ff-only origin main

# ブランチを作る
git switch -c feat/message-search
```

ブランチ名は「種別/内容」で付ける。コミットのプレフィックスと揃えておくと後から追いやすい。

| 種別 | 用途 | 例 |
| --- | --- | --- |
| `feat/` | 機能追加 | `feat/message-search` |
| `fix/` | バグ修正 | `fix/csrf-cookie-expiry` |
| `refactor/` | 挙動を変えない整理 | `refactor/split-auth-service` |
| `ci/` | ワークフロー・CI設定 | `ci/add-markdownlint` |
| `docs/` | ドキュメントのみ | `docs/step12-guide` |

### 2. 実装し、ローカルでCIと同じチェックを回す

CIで落ちてから直すより、手元で潰すほうが速い。CIが実行するのと同じコマンドを流す。

```bash
# backend/ で
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest --cov

# frontend/ で
pnpm install --frozen-lockfile
pnpm lint
pnpm format:check
pnpm typecheck
pnpm test
```

イメージのビルドまで確認したいときは、CIの `docker-build` ジョブと同じものをローカルで作る。

```bash
docker compose --env-file ./backend/.env build backend caddy
```

### 3. コミットする

コミットメッセージは Conventional Commits（`feat:` / `fix:` / `docs:` / `ci:` / `refactor:` / `style:` / `test:`）で書く。

```bash
# 何を含めるか確認してからステージする
git status
git add backend/src/web_practice/routers/messages.py backend/tests/routers/test_messages.py

# ステージした内容を最終確認する
git diff --staged

git commit -m "feat(messages): add keyword search endpoint"
```

> このリポジトリでは `/smart-commit` スキルで、差分からコミットメッセージを生成させることもできる。

### 4. pushしてPull Requestを作る

```bash
# 初回だけ -u で上流ブランチを設定する
git push -u origin feat/message-search

# コミットメッセージからタイトル・本文を埋めてPRを作る
gh pr create --fill

# タイトルと本文を明示する場合
gh pr create --title "feat(messages): キーワード検索を追加" --body "メッセージ一覧にキーワード検索を追加した。"

# まだ完成していないが結果だけ先に見たい場合
gh pr create --draft --fill
```

**PRを作った瞬間にCIが起動する。** ブランチへpushしただけの段階では走らないので、早くCIを回したいときはDraft PRを先に作る。

### 5. CIの結果を確認する

```bash
# 4つのチェックが出揃うまで追う（緑なら exit 0、赤なら exit 1）
gh pr checks --watch

# ブラウザでPR画面を開く
gh pr view --web
```

```text
NAME                       DESCRIPTION  ELAPSED  URL
Backend                    pass         1m20s    https://github.com/.../runs/...
Frontend                   pass         1m05s    https://github.com/.../runs/...
Docker build (backend)     pass         2m10s    https://github.com/.../runs/...
Docker build (frontend)    pass         3m42s    https://github.com/.../runs/...
```

落ちたときは、失敗したステップのログだけを取り出す。

```bash
# 直近の実行を一覧する
gh run list --limit 5

# 失敗したステップのログだけ表示する
gh run view <run id> --log-failed
```

読み方の詳細は 11-3 の「失敗したときの読み方」と「トラブルシューティング」を参照。

### 6. 指摘や失敗を直す

修正コミットを積んで push すれば、そのたびにCIが再実行される（古い実行は自動でキャンセルされる）。

```bash
git add -u
git commit -m "fix(messages): handle empty keyword"
git push
```

`Require branches to be up to date before merging` を有効にしている場合、`main` が先に進むと再度取り込みが必要になる。

```bash
git fetch origin
git rebase origin/main
git push --force-with-lease
```

ブランチ保護の `Block force pushes` は `main` だけが対象なので、作業ブランチへの force push は可能。`--force` ではなく `--force-with-lease` を使い、他人のpushを消さないようにする。

### 7. マージする

```bash
# 全チェックが緑か最終確認する
gh pr checks

# squashでマージし、ローカルとリモートの作業ブランチを削除する
gh pr merge --squash --delete-branch
```

`--delete-branch` は**ローカルブランチも削除する**。ローカルリポジトリ内で実行した場合は、削除前に `main` へ自動で切り替わる。

squashマージなので `main` には1コミットだけ積まれる。**そのコミットSHAがそのままGHCRのイメージタグになり、デプロイ対象になる。**

### 8. デプロイを確認する

マージ＝ `main` へのpushなので、`deploy.yml` が自動で起動する。

```bash
# Deployワークフローの実行を探す
gh run list --workflow=deploy.yml --limit 3

# 実行中のログを追う
gh run watch <run id>
```

Environmentに Required reviewers を設定している場合、`deploy` ジョブは承認待ちで止まる。

```bash
# 承認ボタンのある画面をブラウザで開く
gh run view <run id> --web
```

**Review deployments** → `production` にチェック → **Approve and deploy** で再開する（11-9・11-11 参照）。

完了後の確認。

```bash
# ワークフロー側のスモークテストと同じ確認
curl -i https://taph-lab.com/api/health
curl -i https://taph-lab.com/api/db-health
```

サーバー側で実際に動いているイメージとMigrationを見る手順は、11-11 の「サーバー側の確認」および [docs/dev-commandlist.md](../dev-commandlist.md) の `Deploy / Rollback` にまとめてある。

### 9. ローカルを片付ける

`gh pr merge --delete-branch` を使った場合、ブランチの削除と `main` への切り替えは済んでいる。あとは `main` を最新にするだけ。

```bash
git switch main
git pull --ff-only origin main
```

ブラウザ上でマージした場合や、作業ブランチが残っている場合は手動で片付ける。

```bash
# ローカルの作業ブランチを削除する
git branch -d feat/message-search

# リモートで消えたブランチの追跡情報を掃除する
git fetch --prune origin
```

### Dependabotが作ったPRの扱い

11-12 で `.github/dependabot.yml` を入れたので、毎週、依存とActionの更新PRが自動で作られる。**マージすればそのまま本番へデプロイされる**ため、他のPRと同じようにCIの結果で判断する。

```bash
# Dependabotが作ったPRを一覧する
gh pr list --author "app/dependabot"

# 個別にチェック状況を見る
gh pr checks <PR番号>

# 問題なければマージする
gh pr merge <PR番号> --squash --delete-branch
```

`github-actions` の更新PRは `ci.yml` / `deploy.yml` 自体が書き換わる。特にデプロイ系のAction（`appleboy/ssh-action` など）はオプションが廃止されることがある（11-10 の `script_stop` の例）ので、マージ後の初回デプロイまで見届ける。

### 失敗したときの再実行と切り戻し

```bash
# 失敗したジョブだけ再実行する（一時的なネットワークエラーなど）
gh run rerun <run id> --failed

# ワークフロー全体を再実行する
gh run rerun <run id>

# mainの現在のHEADでデプロイだけを手動実行する
gh workflow run deploy.yml --ref main
```

本番に問題が出たときは、**まずVM上で直前のSHAへ戻して復旧させる**（11-11 の「ロールバック手順」）。

```bash
# VM上で実行
make deploy TAG=<前のcommit sha>
```

復旧したら、GitHub側も同じ状態に揃えるためにrevert用のPRを出す。VM上の切り戻しだけで放置すると、`main` の内容と本番が食い違ったままになる。

```bash
git switch main
git pull --ff-only origin main
git switch -c revert/message-search

# squashマージ後なら、打ち消したいのは main 上の1コミット
git revert <打ち消すcommit sha>
git push -u origin revert/message-search
gh pr create --fill
```

DBのMigrationは自動では戻らない。戻す必要がある場合の手順は「既知の制約」の「Migrationのロールバックは自動化していない」を参照。

### よく使う gh コマンド

| コマンド | 用途 |
| --- | --- |
| `gh pr create --fill` | コミットメッセージからPRを作る |
| `gh pr status` | 自分に関係するPRの状況をまとめて見る |
| `gh pr checks --watch` | CIの結果が出揃うまで待つ |
| `gh pr view --web` | PRをブラウザで開く |
| `gh pr merge --squash --delete-branch` | squashマージしてブランチを削除する |
| `gh run list --workflow=deploy.yml` | Deployワークフローの実行履歴を見る |
| `gh run watch <run id>` | 実行中のワークフローを追う |
| `gh run view <run id> --log-failed` | 失敗したステップのログだけ表示する |
| `gh run rerun <run id> --failed` | 失敗したジョブだけ再実行する |
| `gh workflow run deploy.yml --ref main` | デプロイを手動で起動する |
| `gh browse --settings` | リポジトリのSettingsをブラウザで開く |
