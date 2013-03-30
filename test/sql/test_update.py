from sqlalchemy import *
from sqlalchemy import testing
from sqlalchemy.dialects import mysql
from sqlalchemy.testing import AssertsCompiledSQL, eq_, fixtures
from sqlalchemy.testing.schema import Table, Column


class _UpdateFromTestBase(object):
    @classmethod
    def define_tables(cls, metadata):
        Table('users', metadata,
              Column('id', Integer, primary_key=True,
                     test_needs_autoincrement=True),
              Column('name', String(30), nullable=False))

        Table('addresses', metadata,
              Column('id', Integer, primary_key=True,
                     test_needs_autoincrement=True),
              Column('user_id', None, ForeignKey('users.id')),
              Column('name', String(30), nullable=False),
              Column('email_address', String(50), nullable=False))

        Table('dingalings', metadata,
              Column('id', Integer, primary_key=True,
                     test_needs_autoincrement=True),
              Column('address_id', None, ForeignKey('addresses.id')),
              Column('data', String(30)))

    @classmethod
    def fixtures(cls):
        return dict(
            users=(
                ('id', 'name'),
                (7, 'jack'),
                (8, 'ed'),
                (9, 'fred'),
                (10, 'chuck')
            ),
            addresses = (
                ('id', 'user_id', 'name', 'email_address'),
                (1, 7, 'x', 'jack@bean.com'),
                (2, 8, 'x', 'ed@wood.com'),
                (3, 8, 'x', 'ed@bettyboop.com'),
                (4, 8, 'x', 'ed@lala.com'),
                (5, 9, 'x', 'fred@fred.com')
            ),
            dingalings = (
                ('id', 'address_id', 'data'),
                (1, 2, 'ding 1/2'),
                (2, 5, 'ding 2/5')
            ),
        )


class UpdateFromCompileTest(_UpdateFromTestBase, fixtures.TablesTest,
                            AssertsCompiledSQL):
    __dialect__ = 'default'

    run_create_tables = run_inserts = run_deletes = None

    def test_render_table(self):
        users, addresses = self.tables.users, self.tables.addresses

        self.assert_compile(
            users.update().
                values(name='newname').
                where(users.c.id == addresses.c.user_id).
                where(addresses.c.email_address == 'e1'),
            'UPDATE users '
            'SET name=:name FROM addresses '
            'WHERE '
                'users.id = addresses.user_id AND '
                'addresses.email_address = :email_address_1',
            checkparams={u'email_address_1': 'e1', 'name': 'newname'})

    def test_render_multi_table(self):
        users = self.tables.users
        addresses = self.tables.addresses
        dingalings = self.tables.dingalings

        checkparams = {
            u'email_address_1': 'e1',
            u'id_1': 2,
            'name': 'newname'
        }

        self.assert_compile(
            users.update().
                values(name='newname').
                where(users.c.id == addresses.c.user_id).
                where(addresses.c.email_address == 'e1').
                where(addresses.c.id == dingalings.c.address_id).
                where(dingalings.c.id == 2),
            'UPDATE users '
            'SET name=:name '
            'FROM addresses, dingalings '
            'WHERE '
                'users.id = addresses.user_id AND '
                'addresses.email_address = :email_address_1 AND '
                'addresses.id = dingalings.address_id AND '
                'dingalings.id = :id_1',
            checkparams=checkparams)

    def test_render_table_mysql(self):
        users, addresses = self.tables.users, self.tables.addresses

        self.assert_compile(
            users.update().
                values(name='newname').
                where(users.c.id == addresses.c.user_id).
                where(addresses.c.email_address == 'e1'),
            'UPDATE users, addresses '
            'SET users.name=%s '
            'WHERE '
                'users.id = addresses.user_id AND '
                'addresses.email_address = %s',
            checkparams={u'email_address_1': 'e1', 'name': 'newname'},
            dialect=mysql.dialect())

    def test_render_subquery(self):
        users, addresses = self.tables.users, self.tables.addresses

        checkparams = {
            u'email_address_1': 'e1',
            u'id_1': 7,
            'name': 'newname'
        }

        cols = [
            addresses.c.id,
            addresses.c.user_id,
            addresses.c.email_address
        ]

        subq = select(cols).where(addresses.c.id == 7).alias()
        self.assert_compile(
            users.update().
                values(name='newname').
                where(users.c.id == subq.c.user_id).
                where(subq.c.email_address == 'e1'),
            'UPDATE users '
            'SET name=:name FROM ('
                'SELECT '
                    'addresses.id AS id, '
                    'addresses.user_id AS user_id, '
                    'addresses.email_address AS email_address '
                'FROM addresses '
                'WHERE addresses.id = :id_1'
            ') AS anon_1 '
            'WHERE users.id = anon_1.user_id '
            'AND anon_1.email_address = :email_address_1',
            checkparams=checkparams)


class UpdateFromRoundTripTest(_UpdateFromTestBase, fixtures.TablesTest):

    @testing.requires.update_from
    def test_exec_two_table(self):
        users, addresses = self.tables.users, self.tables.addresses

        testing.db.execute(
            addresses.update().
                values(email_address=users.c.name).
                where(users.c.id == addresses.c.user_id).
                where(users.c.name == 'ed'))

        expected = [
            (1, 7, 'x', 'jack@bean.com'),
            (2, 8, 'x', 'ed'),
            (3, 8, 'x', 'ed'),
            (4, 8, 'x', 'ed'),
            (5, 9, 'x', 'fred@fred.com')]
        self._assert_addresses(addresses, expected)

    @testing.requires.update_from
    def test_exec_two_table_plus_alias(self):
        users, addresses = self.tables.users, self.tables.addresses

        a1 = addresses.alias()
        testing.db.execute(
            addresses.update().
                values(email_address=users.c.name).
                where(users.c.id == a1.c.user_id).
                where(users.c.name == 'ed').
                where(a1.c.id == addresses.c.id)
        )

        expected = [
            (1, 7, 'x', 'jack@bean.com'),
            (2, 8, 'x', 'ed'),
            (3, 8, 'x', 'ed'),
            (4, 8, 'x', 'ed'),
            (5, 9, 'x', 'fred@fred.com')]
        self._assert_addresses(addresses, expected)

    @testing.requires.update_from
    def test_exec_three_table(self):
        users = self.tables.users
        addresses = self.tables.addresses
        dingalings = self.tables.dingalings

        testing.db.execute(
            addresses.update().
                values(email_address=users.c.name).
                where(users.c.id == addresses.c.user_id).
                where(users.c.name == 'ed').
                where(addresses.c.id == dingalings.c.address_id).
                where(dingalings.c.id == 1))

        expected = [
            (1, 7, 'x', 'jack@bean.com'),
            (2, 8, 'x', 'ed'),
            (3, 8, 'x', 'ed@bettyboop.com'),
            (4, 8, 'x', 'ed@lala.com'),
            (5, 9, 'x', 'fred@fred.com')]
        self._assert_addresses(addresses, expected)

    @testing.only_on('mysql', 'Multi table update')
    def test_exec_multitable(self):
        users, addresses = self.tables.users, self.tables.addresses

        values = {
            addresses.c.email_address: users.c.name,
            users.c.name: 'ed2'
        }

        testing.db.execute(
            addresses.update().
                values(values).
                where(users.c.id == addresses.c.user_id).
                where(users.c.name == 'ed'))

        expected = [
            (1, 7, 'x', 'jack@bean.com'),
            (2, 8, 'x', 'ed'),
            (3, 8, 'x', 'ed'),
            (4, 8, 'x', 'ed'),
            (5, 9, 'x', 'fred@fred.com')]
        self._assert_addresses(addresses, expected)

        expected = [
            (7, 'jack'),
            (8, 'ed2'),
            (9, 'fred'),
            (10, 'chuck')]
        self._assert_users(users, expected)

    def _assert_addresses(self, addresses, expected):
        stmt = addresses.select().order_by(addresses.c.id)
        eq_(testing.db.execute(stmt).fetchall(), expected)

    def _assert_users(self, users, expected):
        stmt = users.select().order_by(users.c.id)
        eq_(testing.db.execute(stmt).fetchall(), expected)


class UpdateFromMultiTableUpdateDefaultsTest(_UpdateFromTestBase,
                                             fixtures.TablesTest):
    @classmethod
    def define_tables(cls, metadata):
        Table('users', metadata,
              Column('id', Integer, primary_key=True,
                     test_needs_autoincrement=True),
              Column('name', String(30), nullable=False),
              Column('some_update', String(30), onupdate='im the update'))

        Table('addresses', metadata,
              Column('id', Integer, primary_key=True,
                     test_needs_autoincrement=True),
              Column('user_id', None, ForeignKey('users.id')),
              Column('email_address', String(50), nullable=False))

    @classmethod
    def fixtures(cls):
        return dict(
            users=(
                ('id', 'name', 'some_update'),
                (8, 'ed', 'value'),
                (9, 'fred', 'value'),
            ),
            addresses=(
                ('id', 'user_id', 'email_address'),
                (2, 8, 'ed@wood.com'),
                (3, 8, 'ed@bettyboop.com'),
                (4, 9, 'fred@fred.com')
            ),
        )

    @testing.only_on('mysql', 'Multi table update')
    def test_defaults_second_table(self):
        users, addresses = self.tables.users, self.tables.addresses

        values = {
            addresses.c.email_address: users.c.name,
            users.c.name: 'ed2'
        }

        ret = testing.db.execute(
            addresses.update().
                values(values).
                where(users.c.id == addresses.c.user_id).
                where(users.c.name == 'ed'))

        eq_(set(ret.prefetch_cols()), set([users.c.some_update]))

        expected = [
            (2, 8, 'ed'),
            (3, 8, 'ed'),
            (4, 9, 'fred@fred.com')]
        self._assert_addresses(addresses, expected)

        expected = [
            (8, 'ed2', 'im the update'),
            (9, 'fred', 'value')]
        self._assert_users(users, expected)

    @testing.only_on('mysql', 'Multi table update')
    def test_no_defaults_second_table(self):
        users, addresses = self.tables.users, self.tables.addresses

        ret = testing.db.execute(
            addresses.update().
                values({'email_address': users.c.name}).
                where(users.c.id == addresses.c.user_id).
                where(users.c.name == 'ed'))

        eq_(ret.prefetch_cols(), [])

        expected = [
            (2, 8, 'ed'),
            (3, 8, 'ed'),
            (4, 9, 'fred@fred.com')]
        self._assert_addresses(addresses, expected)

        # users table not actually updated, so no onupdate
        expected = [
            (8, 'ed', 'value'),
            (9, 'fred', 'value')]
        self._assert_users(users, expected)

    def _assert_addresses(self, addresses, expected):
        stmt = addresses.select().order_by(addresses.c.id)
        eq_(testing.db.execute(stmt).fetchall(), expected)

    def _assert_users(self, users, expected):
        stmt = users.select().order_by(users.c.id)
        eq_(testing.db.execute(stmt).fetchall(), expected)
