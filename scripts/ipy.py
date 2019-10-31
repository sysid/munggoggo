import asyncio
import os

import time
from datetime import datetime
import sqlalchemy
from databases import Database
from sqlalchemy import create_engine

# PROJ_PATH = os.getenv('PROJ_DIR')
#
# DB_URL = f'sqlite://{PROJ_PATH}/example.db'
from munggoggo.settings import DB_URL
from munggoggo.model import json_data

print(DB_URL)
engine = create_engine(DB_URL, echo=True)

db = Database(DB_URL)

