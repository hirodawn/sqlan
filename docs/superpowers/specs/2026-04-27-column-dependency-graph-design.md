# Column Dependency Graph — 設計仕様

## 目標

テーブル単位の依存関係グラフを**カラム単位**に昇格させる。具体的には:

- どのカラムとどのカラムが JOIN で結合されているか（実質的な結合キーの特定）
- UPDATE SET 句によってどのカラムの値がどのカラムに流れているか（列コピーフロー）
- Java から注入される値のプレースホルダ名をカラムに紐付けて記録
- SQL ファイルノードはデフォルト非表示にし、ヘッダートグルで必要時に表示

---

## 1. データモデル変更

### 新規: `ColumnUpdate`

```python
@dataclass
class ColumnUpdate:
    sql_file: str
    target_table: str
    target_column: str
    source_table: str | None       # 他テーブルのカラムをコピーする場合
    source_column: str | None      # 同上（source_table と同時に設定）
    placeholder_name: str | None   # /*paramName*/ 形式の Java 注入パラメータ名
```

`source_table/source_column` と `placeholder_name` は排他。どちらも None の場合は定数値代入（追跡対象外）。

### 変更: `SqlAnalysis`

```python
@dataclass
class SqlAnalysis:
    sql_file: str
    read_tables: list[str]
    write_tables: list[str]
    joins: list[JoinInfo]
    column_updates: list[ColumnUpdate]   # 追加
    parse_error: str | None
```

---

## 2. SQL パーサー変更

### `preprocessor.py` — `extract_placeholders()` 追加

前処理（コメント除去）を行う前に、`/*paramName*/` パターンを正規表現でスキャンして辞書を返す。

```python
def extract_placeholders(sql: str) -> dict[str, str]:
    """
    /*paramName*/defaultValue 形式のプレースホルダを抽出する。
    戻り値: {defaultValue_stripped: paramName}
    ただし同じデフォルト値が複数のパラメータで使われる場合は最後のものを優先。
    """
```

コメント除去ロジック（`preprocess_2way_sql`）自体は変更なし。

### `parser.py` — `_extract_column_updates()` 追加

UPDATE 文の SET 句を解析し `ColumnUpdate` リストを生成する。

対象パターン:
1. `SET col = /*param*/'default'` → `placeholder_name="param"`
2. `SET col = alias.other_col`（別テーブル）→ `source_table=解決したテーブル名`, `source_column` を設定
3. `SET col = other_col`（テーブル修飾なし）→ `source_table=target_table`（同一テーブル）, `source_column` を設定

WHERE 句・SELECT 句はスコープ外（値フローの追跡対象はSET句のみ）。

sqlglot の AST で `exp.Update` → `exp.Set` → `exp.EQ` を走査する。左辺が `exp.Column`、右辺が `exp.Column` または識別されたプレースホルダ値。

---

## 3. グラフモデル

### テーブルノード

`cytoscape-node-html-label` プラグイン（CDN）を使い、カスタム HTML をノード内に描画する。

カラム行の表示:
- **▶ カラム名**（黄背景）: JOIN 結合キー（JoinInfo に登場するカラム）
- **✏ カラム名 ← src.col**（橙背景）: UPDATE 書き込み先（列コピー元を付記）
- **✏ カラム名 /\*param\*/**（橙背景）: UPDATE 書き込み先（パラメータ注入）
- カラム名（グレー）: その他

ノードのデータに `columns` 配列を含める:

```json
{
  "id": "table:EMPLOYEE",
  "type": "table",
  "label": "EMPLOYEE",
  "row_count": 1500,
  "columns": [
    {
      "name": "EMP_ID",
      "is_join_key": true,
      "is_update_target": false,
      "placeholder_name": null,
      "update_source": null
    },
    {
      "name": "DEPT_CD",
      "is_join_key": false,
      "is_update_target": true,
      "placeholder_name": "deptCd",
      "update_source": null
    },
    {
      "name": "NAME",
      "is_join_key": false,
      "is_update_target": true,
      "placeholder_name": null,
      "update_source": "DEPARTMENT.DEPT_NAME"  // グラフビルダーが source_table + "." + source_column を結合
    }
  ]
}
```

### エッジ

| type | 色 | 方向 | ラベル | 追加データ |
|---|---|---|---|---|
| `join` | 赤 `#e94560` | 無向 | `LEFT_COL = RIGHT_COL` | `sql_files: [...]` |
| `column_copy` | 水色 `#1ab4b4` | 有向（source→target） | `src.col → tgt.col` | `sql_files: [...]` |
| `read` | 緑 `#4a8b6b` | 有向（sql→table） | — | SQLトグル時のみ表示 |
| `write` | 橙 `#e9a020` | 有向（sql→table） | — | SQLトグル時のみ表示 |

JOIN エッジと列コピーエッジには `sql_files` 配列を付与し、クリック時の詳細パネルで参照元 SQL を表示できるようにする。

---

## 4. フロントエンド

### ヘッダー追加コントロール

既存ヘッダーに以下を追加:

```
[SQLファイルを表示  ○──]   ← トグルスイッチ（デフォルト OFF）
```

OFF 時: `type="sql_file"` のノードと `type="read"/"write"` のエッジを非表示（`display: none`）。
ON 時: 表示。再レイアウトは行わない（グラフ再構築ではなく表示切替のみ）。

### クリック時の詳細パネル

**テーブルノードクリック:**
- テーブル名・行数
- カラム一覧（役割付き）
- このテーブルを参照する SQL ファイル一覧（ファイル名・SELECT/UPDATE 種別）

**JOIN エッジクリック:**
- 結合条件: `TABLE_A.COL_X = TABLE_B.COL_Y`
- FK 制約の有無
- このJOINを行う SQL ファイル一覧

**列コピーエッジクリック:**
- コピー元カラム / コピー先カラム
- このUPDATEを行うSQL ファイル一覧
- Java 呼び出しクラス・メソッド

### ノードの HTML 描画

`cytoscape-node-html-label` を CDN から読み込み、テーブルノードに ER 図スタイルのHTMLを描画する。ノードの高さはカラム数に応じて動的に決まる。大規模グラフ（ノード数 > 150）でも適用するが、カラム行はデフォルト展開とする。

---

## 5. グラフビルダー変更

`GraphBuilder.build()` で以下を生成:

1. テーブルノード: `columns` 配列に役割フラグを付与
2. JOIN エッジ: `label`, `sql_files` を追加
3. 列コピーエッジ（新規）: `column_updates` から `source_table` が存在するものを抽出
4. SQL ファイルノード: 引き続き生成（表示制御はフロントエンドが担う）

`column_updates` のうち `placeholder_name` のみのもの（パラメータ注入）はエッジにせず、対象テーブルノードの `columns[].placeholder_name` に記録するのみ。

---

## 6. 変更対象ファイル一覧

| ファイル | 変更種別 |
|---|---|
| `analyzer/models.py` | `ColumnUpdate` 追加、`SqlAnalysis.column_updates` 追加 |
| `analyzer/sql_parser/preprocessor.py` | `extract_placeholders()` 追加 |
| `analyzer/sql_parser/parser.py` | `_extract_column_updates()` 追加 |
| `analyzer/graph_builder/builder.py` | ノード拡張、列コピーエッジ追加、sql_files 付与 |
| `web/frontend/index.html` | cytoscape-node-html-label 追加、SQL トグル、詳細パネル拡張 |

**変更なし:** `java_scanner/`、`db_inspector/`、`web/routes.py`、`web/app.py`

---

## 7. スコープ外

- WHERE 句のカラム条件（フィルタ条件の可視化）
- INSERT SELECT の値フロー（INSERT INTO SELECT FROM パターン）
- カラムのデータ型・制約表示
- カラム単位の行数/カーディナリティ
