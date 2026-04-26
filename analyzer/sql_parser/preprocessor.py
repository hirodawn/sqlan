import re

def preprocess_2way_sql(sql: str) -> str:
    # Seasar2の特殊コメント /*...*/ を除去する。
    # /*IF*/, /*END*/, /*BEGIN*/, /*paramName*/ をすべてこの1パスで処理できる。
    # /*paramName*/defaultValue の場合、コメントだけが除去されデフォルト値が残る。
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    # 行コメント形式のSeasar2ディレクティブ: --IF, --ELSE, --END（直前の空白も除去）
    sql = re.sub(r'[ \t]*--(?:IF|ELSE|END)[^\n]*', '', sql)
    # 行末の残余スペースを除去
    sql = re.sub(r'[ \t]+$', '', sql, flags=re.MULTILINE)
    # 連続する空白を整理（改行は保持）
    sql = re.sub(r'[ \t]+', ' ', sql)
    sql = re.sub(r'\n{3,}', '\n\n', sql)
    return sql.strip()
