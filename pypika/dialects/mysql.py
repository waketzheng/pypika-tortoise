from __future__ import annotations

import json
from datetime import time
from typing import Any, cast

from pypika.enums import Dialects
from pypika.queries import Query, QueryBuilder, Table
from pypika.terms import ValueWrapper
from pypika.utils import builder, format_alias_sql, format_quotes


class MySQLQuery(Query):
    """
    Defines a query class for use with MySQL.
    """

    @classmethod
    def _builder(cls, **kwargs: Any) -> "MySQLQueryBuilder":
        return MySQLQueryBuilder(**kwargs)

    @classmethod
    def load(cls, fp: str) -> "MySQLLoadQueryBuilder":
        return MySQLLoadQueryBuilder().load(fp)


class MySQLValueWrapper(ValueWrapper):
    def get_value_sql(self, **kwargs: Any) -> str:
        quote_char = kwargs.get("secondary_quote_char") or ""
        if isinstance(value := self.value, str):
            value = value.replace(quote_char, quote_char * 2)
            value = value.replace("\\", "\\\\")
            return format_quotes(value, quote_char)
        elif isinstance(value, time):
            value = value.replace(tzinfo=None)
            return format_quotes(value.isoformat(), quote_char)
        elif isinstance(value, (dict, list)):
            value = format_quotes(json.dumps(value), quote_char)
            return value.replace("\\", "\\\\")
        return super().get_value_sql(**kwargs)


class MySQLQueryBuilder(QueryBuilder):
    QUOTE_CHAR = "`"
    QUERY_CLS = MySQLQuery

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            dialect=Dialects.MYSQL,
            wrapper_cls=MySQLValueWrapper,
            wrap_set_operation_queries=False,
            **kwargs,
        )
        self._modifiers: list[str] = []

    def _on_conflict_sql(self, **kwargs: Any) -> str:
        kwargs["alias_quote_char"] = (
            self.ALIAS_QUOTE_CHAR
            if self.QUERY_ALIAS_QUOTE_CHAR is None
            else self.QUERY_ALIAS_QUOTE_CHAR
        )
        kwargs["as_keyword"] = True
        querystring = format_alias_sql("", self.alias, **kwargs)
        return querystring

    def get_sql(self, **kwargs: Any) -> str:  # type:ignore[override]
        self._set_kwargs_defaults(kwargs)
        querystring = super().get_sql(**kwargs)
        if querystring and self._update_table:
            if self._orderbys:
                querystring += self._orderby_sql(**kwargs)
            if self._limit:
                querystring += self._limit_sql()
        return querystring

    def _on_conflict_action_sql(self, **kwargs: Any) -> str:
        kwargs.pop("with_namespace", None)
        if len(self._on_conflict_do_updates) > 0:
            updates = []
            for field, value in self._on_conflict_do_updates:
                if value:
                    updates.append(
                        "{field}={value}".format(
                            field=field.get_sql(**kwargs),
                            value=value.get_sql(**kwargs),
                        )
                    )
                else:
                    updates.append(
                        "{field}={alias}.{value}".format(
                            field=field.get_sql(**kwargs),
                            alias=format_quotes(self.alias, self.QUOTE_CHAR),
                            value=field.get_sql(**kwargs),
                        )
                    )
            action_sql = " ON DUPLICATE KEY UPDATE {updates}".format(updates=",".join(updates))
            return action_sql
        return ""

    @builder
    def modifier(self, value: str) -> MySQLQueryBuilder:  # type:ignore[return]
        """
        Adds a modifier such as SQL_CALC_FOUND_ROWS to the query.
        https://dev.mysql.com/doc/refman/5.7/en/select.html

        :param value: The modifier value e.g. SQL_CALC_FOUND_ROWS
        """
        self._modifiers.append(value)

    def _select_sql(self, **kwargs: Any) -> str:
        """
        Overridden function to generate the SELECT part of the SQL statement,
        with the addition of the a modifier if present.
        """
        return "SELECT {distinct}{modifier}{select}".format(
            distinct="DISTINCT " if self._distinct else "",
            modifier="{} ".format(" ".join(self._modifiers)) if self._modifiers else "",
            select=",".join(
                term.get_sql(with_alias=True, subquery=True, **kwargs) for term in self._selects
            ),
        )

    def _insert_sql(self, **kwargs: Any) -> str:
        insert_table = cast(Table, self._insert_table)
        return "INSERT {ignore}INTO {table}".format(
            table=insert_table.get_sql(**kwargs),
            ignore="IGNORE " if self._on_conflict_do_nothing else "",
        )


class MySQLLoadQueryBuilder:
    QUERY_CLS = MySQLQuery

    def __init__(self) -> None:
        self._load_file: str | None = None
        self._into_table: Table | None = None

    @builder
    def load(self, fp: str) -> MySQLLoadQueryBuilder:  # type:ignore[return]
        self._load_file = fp

    @builder
    def into(self, table: str | Table) -> MySQLLoadQueryBuilder:  # type:ignore[return]
        self._into_table = table if isinstance(table, Table) else Table(table)

    def get_sql(self, *args: Any, **kwargs: Any) -> str:
        querystring = ""
        if self._load_file and self._into_table:
            querystring += self._load_file_sql(**kwargs)
            querystring += self._into_table_sql(**kwargs)
            querystring += self._options_sql(**kwargs)

        return querystring

    def _load_file_sql(self, **kwargs: Any) -> str:
        return "LOAD DATA LOCAL INFILE '{}'".format(self._load_file)

    def _into_table_sql(self, **kwargs: Any) -> str:
        table = cast(Table, self._into_table)
        return " INTO TABLE `{}`".format(table.get_sql(**kwargs))

    def _options_sql(self, **kwargs: Any) -> str:
        return " FIELDS TERMINATED BY ','"

    def __str__(self) -> str:
        return self.get_sql()
