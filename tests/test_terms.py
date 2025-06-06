from unittest import TestCase

from pypika_tortoise import Field, Query, Table
from pypika_tortoise.context import DEFAULT_SQL_CONTEXT
from pypika_tortoise.terms import AtTimezone, Parameterizer, ValueWrapper


class FieldAliasTests(TestCase):
    t = Table("test", alias="crit")

    def test_when_alias_specified(self):
        c1 = Field("foo", alias="bar")
        self.assertEqual("bar", str(c1.alias))

        c1 = Field("foo").as_("bar")
        self.assertEqual("bar", str(c1.alias))


class AtTimezoneTests(TestCase):
    def test_when_interval_not_specified(self):
        query = Query.from_("customers").select(AtTimezone("date", "US/Eastern"))
        self.assertEqual('SELECT "date" AT TIME ZONE \'US/Eastern\' FROM "customers"', str(query))

    def test_when_interval_specified(self):
        query = Query.from_("customers").select(AtTimezone("date", "-06:00", interval=True))
        self.assertEqual(
            'SELECT "date" AT TIME ZONE INTERVAL \'-06:00\' FROM "customers"',
            str(query),
        )

    def test_when_alias_specified(self):
        query = Query.from_("customers").select(AtTimezone("date", "US/Eastern", alias="alias1"))
        self.assertEqual(
            'SELECT "date" AT TIME ZONE \'US/Eastern\' "alias1" FROM "customers"',
            str(query),
        )

    def test_passes_kwargs_to_field_get_sql(self):
        customers = Table("customers")
        accounts = Table("accounts")
        query = (
            Query.from_(customers)
            .join(accounts)
            .on(customers.account_id == accounts.account_id)
            .select(AtTimezone(customers.date, "US/Eastern", alias="alias1"))
        )

        self.assertEqual(
            'SELECT "customers"."date" AT TIME ZONE \'US/Eastern\' "alias1" '
            'FROM "customers" JOIN "accounts" ON "customers"."account_id"="accounts"."account_id"',
            query.get_sql(DEFAULT_SQL_CONTEXT.copy(with_namespace=True)),
        )


class ValueWrapperTests(TestCase):
    def test_allow_parametrize(self):
        value = ValueWrapper("foo")
        self.assertEqual("'foo'", value.get_sql(DEFAULT_SQL_CONTEXT))

        value = ValueWrapper("foo")
        self.assertEqual(
            "?", value.get_sql(DEFAULT_SQL_CONTEXT.copy(parameterizer=Parameterizer()))
        )

        value = ValueWrapper("foo", allow_parametrize=False)
        self.assertEqual(
            "'foo'", value.get_sql(DEFAULT_SQL_CONTEXT.copy(parameterizer=Parameterizer()))
        )
