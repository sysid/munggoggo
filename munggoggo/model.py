import logging
from contextlib import closing

from sqlalchemy import (
    Column,
    Table,
    Integer,
    String,
    Boolean,
    JSON,
    MetaData,
    create_engine,
    TIMESTAMP,
    Text,
)
from sqlalchemy.engine import Connection
from sqlalchemy_utils import database_exists, create_database, drop_database

from settings import DB_URL

_log = logging.getLogger(__name__)

metadata = MetaData()

# ATTENTION: keep in sync with SqlBehviour.json_data definition !!!
json_data = Table(
    "json_data",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("ts", TIMESTAMP(timezone=True)),
    Column("sender", String(length=256)),
    Column("rmq_type", String(length=100)),
    Column("content_type", String(length=100)),
    Column("routing_key", String(length=256)),
    Column("data", JSON),
)


class TsDb(object):
    def __init__(self, url: str, meta: MetaData, *args, **kwargs):
        # global metadata
        self.url = url

        # The engine object is a repository for database connections capable of issuing SQL to the database.
        # To acquire a connection, we use the connect() method:
        self.engine = create_engine(url, echo=True)
        self.meta = meta
        # metadata.bind = self.engine

    @staticmethod
    def create_new_db(url) -> None:
        _log.info(url)

        if not database_exists(url):
            create_database(url)

        _log.info(f"{url}: {database_exists(url)}")

    # You cannot be connected to the database you are about to remove.
    # Instead, connect to template1 or any other database and run this command again.
    # conn.execute(f"drop database if exists {dbname}")
    def drop_db(self):
        if database_exists(self.engine.url):
            drop_database(self.engine.url)

    # you can only connect to a existing DB !!
    def connect(self) -> Connection:
        if database_exists(self.engine.url):
            return self.engine.connect()

    def test_connect(self) -> bool:

        conn = self.connect()
        if conn is None:
            return False

        with closing(conn) as conn:
            try:
                qry = conn.execute("SELECT 1")
            except Exception as e:
                print(e)
                return False
            return True

    def init_db(self) -> None:
        self.meta.create_all(bind=self.engine, checkfirst=True)

    def reset_db(self) -> None:
        self.meta.drop_all(bind=self.engine)
        self.meta.create_all(bind=self.engine, checkfirst=True)

    def has_table(self, name) -> bool:
        return self.meta.tables.get(name) is not None
