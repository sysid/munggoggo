import os
from contextlib import closing
from pathlib import Path

import pytest
from databases import Database

from model import TsDb, json_data, metadata
from settings import DB_URL, SQLITE_PATH


@pytest.fixture()
def rm_sqlite():
    path = Path(SQLITE_PATH)
    if path.exists():
        os.remove(path)


@pytest.fixture()
def db(rm_sqlite):
    # path = Path(SQLITE_PATH)
    # if path.exists():
    #     os.remove(path)
    TsDb.create_new_db(DB_URL)
    return TsDb(url=DB_URL, meta=metadata)


@pytest.fixture()
async def adb(db):
    db.init_db()
    assert db.test_connect()
    adb = Database(DB_URL)
    await adb.connect()

    yield adb

    await adb.disconnect()


def test_create_new_db(db):
    assert db.test_connect()


# TODO: init_db creates Text instead of JSON
def test_has_table(db):
    db.init_db()
    assert db.has_table('json_data')
    db.reset_db()
    assert db.has_table('json_data')


@pytest.mark.skip("works isolated. confusiong with regards to Text vs. JSON datatype")
def test_sync_insert(db, json_data_values):
    db.init_db()
    json_data.insert()
    with closing(db.connect()) as conn:
        conn.execute(json_data.insert(), json_data_values)

        # result = conn.execute(select([json_data]))
        # assert len(list(result)) == len(json_data_values)
        #
        # query = select([json_data]).where(
        #     cast(json_data.c.data['a'], String) == type_coerce("aaa", JSON)
        # )
        # result = conn.execute(query)
        # assert len(list(result)) == 1


@pytest.mark.asyncio
class TestDatabase:
    @pytest.mark.skip("works isolated. confusiong with regards to Text vs. JSON datatype")
    async def test_insert(self, adb, json_data_values):
        query = json_data.insert()
        await adb.execute_many(query=query, values=json_data_values)

        query = json_data.select()
        rows = await adb.fetch_all(query=query)
        assert len(rows) == len(json_data_values)
