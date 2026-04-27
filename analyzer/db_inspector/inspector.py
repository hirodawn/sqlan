import logging
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from analyzer.models import TableInfo, ForeignKey

logger = logging.getLogger(__name__)


class DBInspector:
    def __init__(self, engine: Engine):
        self.engine = engine

    def get_row_count(self, table_name: str) -> int:
        try:
            with self.engine.connect() as conn:
                return conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
        except Exception as e:
            logger.warning("get_row_count 失敗 [%s]: %s", table_name, e)
            return -1

    def get_column_cardinality(self, table_name: str, column_name: str) -> int:
        try:
            with self.engine.connect() as conn:
                return conn.execute(
                    text(f"SELECT COUNT(DISTINCT {column_name}) FROM {table_name}")
                ).scalar()
        except SQLAlchemyError:
            return -1

    def get_foreign_keys(self, table_name: str) -> list[ForeignKey]:
        try:
            insp = inspect(self.engine)
            # Oracle では大文字テーブル名でリトライ
            for lookup in [table_name, table_name.upper()]:
                try:
                    fks = insp.get_foreign_keys(lookup)
                    if fks or lookup == table_name.upper():
                        return [
                            ForeignKey(
                                from_table=table_name,
                                from_column=fk["constrained_columns"][0],
                                to_table=fk["referred_table"],
                                to_column=fk["referred_columns"][0],
                                has_fk_constraint=True,
                            )
                            for fk in fks
                            if fk.get("constrained_columns") and fk.get("referred_columns")
                        ]
                except SQLAlchemyError:
                    continue
        except SQLAlchemyError:
            pass
        return []

    def _get_columns(self, insp, table_name: str) -> list[str]:
        # Oracle ではデータディクショナリのテーブル名が大文字で保存されるため、
        # 小文字名で失敗した場合は大文字でリトライする。
        for lookup in [table_name, table_name.upper()]:
            try:
                cols = insp.get_columns(lookup)
                if cols:
                    logger.debug("_get_columns 成功 [%s] -> %d列", lookup, len(cols))
                    return [col["name"] for col in cols]
            except Exception as e:
                logger.warning("_get_columns 失敗 [%s]: %s", lookup, e)
        return []

    def get_table_info(self, table_name: str) -> TableInfo:
        # row_count=-1 は DB接続失敗またはテーブル不存在を表すセンチネル値。
        # UI側はこの値を「不明」として表示する（index.html 参照）。
        try:
            insp = inspect(self.engine)
            columns = self._get_columns(insp, table_name)
        except Exception as e:
            logger.warning("get_table_info inspect 失敗 [%s]: %s", table_name, e)
            columns = []
        return TableInfo(
            name=table_name,
            row_count=self.get_row_count(table_name),
            columns=columns,
        )

    def inspect_tables(self, table_names: list[str]) -> dict[str, TableInfo]:
        return {name: self.get_table_info(name) for name in table_names}
