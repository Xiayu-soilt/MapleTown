import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="mapletown_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db".replace("\\", "/")
os.environ["EMBEDDING_PROVIDER"] = "hashing"
os.environ["CHROMA_DIR"] = ":memory:"

import datetime as dt

import pytest

from app.models.world import Resident

T0 = dt.datetime(2026, 9, 14, 8, 0)


@pytest.fixture
def db():
    from app.cognition.vector_store import vector_store
    from app.db.session import SessionLocal, engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
    vector_store.clear()


@pytest.fixture
def resident(db):
    r = Resident(
        name="林小满",
        age=28,
        persona={"identity": "面包师", "goal": "研发新口味的面包"},
        workplace="满堂香面包房",
        current_activity="揉面团",
    )
    db.add(r)
    db.flush()
    return r
