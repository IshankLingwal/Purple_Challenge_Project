import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import init_db, SessionLocal, events_table


@pytest.fixture()
def client():
    init_db()

    # Clear previous test / manual run data
    with SessionLocal() as session:
        session.execute(events_table.delete())
        session.commit()

    with TestClient(app) as test_client:
        yield test_client