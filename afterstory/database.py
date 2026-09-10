from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from afterstory.config import Settings


def make_sessions(settings: Settings):
    engine = create_engine(settings.database_url.get_secret_value(), pool_pre_ping=True)
    return engine, sessionmaker(engine, expire_on_commit=False)
