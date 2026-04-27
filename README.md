# sqlan

JavaアプリケーションのS2JDBC 2-way SQLファイルを解析し、DBの実データと照合することで**真のデータ依存関係**をインタラクティブに可視化するWebアプリケーション。

![スクリーンショット](docs/screenshot.png)

## 概要

レガシーJavaシステムでは、SQLがソースコードではなく外部ファイル（S2JDBC 2-way SQL形式）に分散しており、「どのSQLがどのテーブルを読み書きしているか」「テーブル間のFK関係はどうなっているか」をコードから把握するのが困難です。

sqlanはこの問題を解決します。

- **Javaソースを静的解析** → SQLファイルへの参照を自動抽出
- **2-way SQLを前処理** → `/*IF*/`, `/*END*/`, `/*BEGIN*/` などのSeasar2構文を除去してsqlglotで解析
- **DBに接続して実データを収集** → FK制約・行数・カーディナリティ
- **Cytoscape.jsでインタラクティブ表示** → ノードクリックで詳細確認、絞り込み、レイアウト切り替え

## ユースケース

- レガシーシステムのリバースエンジニアリング・仕様理解
- リファクタリング・テーブル設計変更前の影響調査
- 日常的な開発時のSQL/テーブル依存確認

## スクリーンショット

```
┌─────────────────────────────────────────────────────┐
│ [検索バー]  [フィルター▼]  [レイアウト▼]  [解析実行]  │
├──────────────────────────────┬──────────────────────┤
│                              │                      │
│   Cytoscape.jsグラフ         │   詳細パネル         │
│                              │  選択中: orders      │
│   ○ テーブルノード           │  行数: 1,234,567     │
│   □ SQLファイルノード        │  参照SQL: 12件       │
│   ─ JOIN関係エッジ           │  FK: customer_id     │
│   ─ READ/WRITEエッジ         │  カーディナリティ:   │
│                              │  customers 1:N       │
└──────────────────────────────┴──────────────────────┘
```

## 技術スタック

| 役割 | 技術 |
|------|------|
| SQL解析 | [sqlglot](https://github.com/tobymao/sqlglot) |
| DB接続 | SQLAlchemy 2.x（MySQL / PostgreSQL / Oracle 等） |
| APIサーバー | FastAPI + uvicorn |
| グラフ可視化 | Cytoscape.js |
| フロントエンド | Plain HTML + Vanilla JS |
| 設定ファイル | TOML |

## インストール

Python 3.11以上が必要です。

```bash
git clone https://github.com/hirodawn/sqlan.git
cd sqlan
pip install -r requirements.txt
```

## 設定

`config.toml` を編集してJavaプロジェクトのパスとDB接続情報を設定します。

```toml
[source]
java_root = "/path/to/your/java/project/src"
sql_root  = "/path/to/your/java/project/src/main/resources"

[database]
url = "mysql+pymysql://user:password@localhost:3306/mydb"
# url = "postgresql+psycopg2://user:password@localhost:5432/mydb"
# url = "oracle+cx_oracle://user:password@localhost:1521/mydb"
# DBなしで静的解析のみ行う場合は url を空文字列にしてください

[analysis]
timeout_seconds    = 300
cardinality_sample = 10000
```

## 起動

```bash
python main.py config.toml
```

ブラウザで `http://localhost:8000` を開き、「解析実行」ボタンをクリックします。

## 機能

### グラフ表示

- **テーブルノード**（丸）: テーブル名・行数・参照SQLファイル数を表示
- **SQLファイルノード**（四角）: ファイル名・操作種別（SELECT/UPDATE/INSERT/DELETE）・呼び出しクラス名を表示
- **JOINエッジ**（赤）: JOIN条件・FK制約の有無を表示
- **READエッジ**（緑）: SQLファイル → テーブルの読み取り参照
- **WRITEエッジ**（橙）: SQLファイル → テーブルの書き込み参照

### インタラクション

- **ノード/エッジクリック**: 詳細パネルに情報を表示
- **検索バー**: テーブル名・SQLファイル名でリアルタイム絞り込み
- **操作種別フィルター**: SELECT / UPDATE / INSERT / WRITE で絞り込み
- **レイアウト切り替え**: force-directed / 階層型 / グリッド / 円形

### API

| メソッド | パス | 内容 |
|----------|------|------|
| `GET` | `/api/health` | ヘルスチェック |
| `POST` | `/api/analyze` | 解析実行（ジョブID返却） |
| `GET` | `/api/status/{job_id}` | 解析進捗確認 |
| `GET` | `/api/graph/{job_id}` | グラフJSON取得 |
| `GET` | `/api/node/{node_id}` | ノード詳細取得 |

## アーキテクチャ

```
Javaソース群（.javaファイル）
    ↓ java_scanner（正規表現パターンマッチ）
SQLファイルパス一覧 + 呼び出しクラス/メソッド情報
    ↓ sql_parser（S2JDBC前処理 → sqlglot AST解析）
テーブル参照・JOIN条件・操作種別の構造データ
    ↓ db_inspector（SQLAlchemy + INFORMATION_SCHEMA + 実データ集計）
カーディナリティ・FK実態・行数
    ↓ graph_builder
依存グラフJSON（Cytoscape.js形式）
    ↓ Web UI（Cytoscape.js）
インタラクティブ可視化
```

## テスト

```bash
pytest tests/ -v
```

39テスト、SQLite in-memory DBを使用してCIでも動作します。

## S2JDBC 2-way SQL対応構文

| 構文 | 処理 |
|------|------|
| `/*IF condition*/` | 除去 |
| `/*END*/` | 除去 |
| `/*BEGIN*/` | 除去 |
| `/*paramName*/defaultValue` | コメント除去・デフォルト値を残す |

## ライセンス

MIT
