# SQL依存関係アナライザー 設計ドキュメント

**作成日:** 2026-04-26  
**ステータス:** 承認済み

---

## 概要

JavaアプリケーションのS2JDBC 2-way SQLファイルを解析し、DBの実データと照合することで真のデータ依存関係をインタラクティブに可視化するWebアプリケーション。

### 対象ユースケース
- レガシーシステムのリバースエンジニアリング・仕様理解
- リファクタリング・テーブル設計変更前の影響調査
- 日常的な開発時のSQL/テーブル依存確認

### 想定規模
- 最大：SQLファイル千個以上、テーブル数百個以上
- あらゆる規模のプロジェクトで動作すること

---

## アーキテクチャ

### ディレクトリ構成

```
sqlan/
├── analyzer/
│   ├── java_scanner/   # Javaソースから2-way SQLファイル参照を抽出
│   ├── sql_parser/     # 2-way SQL前処理 + sqlglot解析
│   ├── db_inspector/   # DB接続・実データ解析
│   └── graph_builder/  # 依存グラフ構築
├── web/
│   ├── api/            # FastAPI REST API
│   └── frontend/       # Cytoscape.js インタラクティブUI
├── tests/
│   └── fixtures/       # テスト用サンプルJavaプロジェクト・SQLファイル
├── docs/
└── config.toml         # DB接続情報・解析対象パス設定
```

### データフロー

```
Javaソース群（.javaファイル）
    ↓ java_scanner（パターンマッチ）
SQLファイルパス一覧 + 呼び出しクラス/メソッド情報
    ↓ sql_parser（S2JDBC前処理 → sqlglot AST解析）
テーブル参照・JOIN条件・操作種別の構造データ
    ↓ db_inspector（SQLAlchemy + INFORMATION_SCHEMA + 実データ集計）
カーディナリティ・FK実態・行数・孤立レコード数
    ↓ graph_builder
依存グラフJSON（ノード=テーブル/SQLファイル、エッジ=依存関係+実データ付き）
    ↓ Web UI（Cytoscape.js）
インタラクティブ可視化
```

### 主要技術スタック

| 役割 | 技術 |
|------|------|
| 言語 | Python 3.11+ |
| SQL解析 | sqlglot |
| DB接続 | SQLAlchemy 2.x（MySQL / PostgreSQL / Oracle 等） |
| APIサーバー | FastAPI |
| グラフ可視化 | Cytoscape.js |
| フロントエンド | Plain HTML + Vanilla JS（フレームワークなし）、FastAPIで静的配信 |
| 設定ファイル | TOML |
| 非同期処理 | asyncio |

---

## コンポーネント詳細

### 1. `java_scanner` — Javaソース解析

**役割:** `.java` ファイルを再帰走査し、S2JDBCの呼び出しパターンからSQLファイル参照を抽出する。

**抽出対象パターン（例）:**
```java
sqlManager.getResultList(Employee.class, "META-INF/sql/selectEmployee.sql", dto);
```

**抽出情報:**
- SQLファイルパス（文字列リテラル）
- 呼び出しクラス名・メソッド名
- 操作種別（SELECT / UPDATE / INSERT / DELETE）

**実装方針:** 正規表現によるパターンマッチ。S2JDBCの呼び出し規約（`SqlFileSelectQuery`, `SqlFileUpdateQuery` 等）はパターンが一定なため、ASTベースの解析は不要。

---

### 2. `sql_parser` — 2-way SQL解析

**役割:** S2JDBC 2-way SQL固有の構文を標準SQLに前処理し、sqlglotでAST解析する。

**前処理（正規表現）:**

| S2JDBC構文 | 変換後 |
|-----------|--------|
| `/*IF condition*/` | 除去 |
| `/*END*/` | 除去 |
| `/*BEGIN*/` | 除去 |
| `/*paramName*/defaultValue` | `:paramName`（名前付きパラメータ） |

**sqlglotで抽出する情報:**
- 参照テーブル一覧（FROM / JOIN 句）
- JOIN条件（結合カラム）
- WHERE条件で使われているカラム
- INSERT / UPDATE 対象カラム

---

### 3. `db_inspector` — 実データ解析

**役割:** DBに接続し、SQLが参照するテーブルの実データ情報を収集する。

**収集情報:**
- `INFORMATION_SCHEMA` からのFK制約・インデックス情報
- 各テーブルの行数
- JOIN対象カラムの実カーディナリティ（`COUNT(DISTINCT col)`）
- FK宣言がなくても実データから関連を推定（カラム名・値の一致度）

**接続設定:** `config.toml` にJDBC互換の接続情報（host / port / DB名 / 認証情報）を記載。

**`config.toml` サンプル:**
```toml
[source]
java_root = "/path/to/your/java/project/src"
sql_root  = "/path/to/your/java/project/src/main/resources"

[database]
url      = "mysql+pymysql://user:password@localhost:3306/mydb"
# url = "postgresql+psycopg2://user:password@localhost:5432/mydb"
# url = "oracle+cx_oracle://user:password@localhost:1521/mydb"

[analysis]
timeout_seconds     = 300
cardinality_sample  = 10000  # COUNT(DISTINCT)のサンプル行数上限
```

---

### 4. `graph_builder` — グラフ構築

**役割:** 各コンポーネントの出力を統合し、Cytoscape.js向けのグラフJSONを生成する。

**ノード定義:**

| ノード種別 | 属性 |
|-----------|------|
| テーブル | テーブル名・行数・参照SQLファイル数 |
| SQLファイル | ファイルパス・操作種別・呼び出しクラス名 |

**エッジ定義:**

| エッジ種別 | 属性 |
|-----------|------|
| テーブル間 | JOIN条件・実カーディナリティ・FK制約の有無 |
| SQLファイル → テーブル | READ / WRITE 種別 |

---

## Web UI

### 画面レイアウト

```
┌─────────────────────────────────────────────────────┐
│ [検索バー]  [フィルター▼]  [レイアウト▼]  [再解析]  │
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

### インタラクション

- **ノードクリック:** 詳細パネルに実データ情報・関連SQLファイル一覧を表示
- **エッジクリック:** JOIN条件・実カーディナリティ・FK制約の有無を表示
- **フィルター:** テーブル名・SQLファイル名・操作種別（READ/WRITE）で絞り込み
- **レイアウト切り替え:** 階層型 / force-directed / グリッド
- **再解析ボタン:** バックエンドで差分解析を再実行してグラフを更新

### APIエンドポイント

| メソッド | パス | 内容 |
|----------|------|------|
| `POST` | `/api/analyze` | 解析実行（設定ファイルのパスを受け取る） |
| `GET` | `/api/graph` | グラフJSON全体を返す |
| `GET` | `/api/node/{name}` | テーブル/SQLノードの詳細情報 |
| `GET` | `/api/status` | 解析進捗（大規模対応用ポーリング） |

---

## 大規模対応

- 解析はバックグラウンド非同期実行（`/api/status` でポーリング）
- グラフ初期表示は「テーブルノードのみ」、SQLノードはオンデマンド展開
- Cytoscape.jsの仮想レンダリングで大規模グラフのパフォーマンスを確保

---

## エラー処理

| 状況 | 対応 |
|------|------|
| 2-way SQL前処理で構文が崩れる | ファイルパス・行番号付きで警告ログに記録し、そのファイルをスキップ |
| sqlglotが解析できないSQL方言 | フォールバック：正規表現でテーブル名のみ抽出 |
| DB接続失敗 | 静的解析（SQLファイル＋Javaソース）のみで部分グラフを生成 |
| テーブルが存在しない | グラフ上で「未確認ノード」として明示 |
| 解析が長時間かかる | タイムアウト設定可能、部分完了状態でもグラフを表示可 |

---

## テスト戦略

### ユニットテスト（pytest）

- `sql_parser`: 代表的な2-way SQLパターン（IF/END/BEGIN/パラメータ）の前処理と解析結果
- `java_scanner`: S2JDBCの各呼び出しパターンからのファイルパス抽出
- `graph_builder`: ノード・エッジの構築ロジック

### 統合テスト

- SQLiteを使ったDBインスペクターの動作確認（CI環境で動作）
- テスト用最小Javaプロジェクトを `tests/fixtures/` に同梱

### 手動確認

- 大規模プロジェクトでの解析速度・UI描画パフォーマンス
