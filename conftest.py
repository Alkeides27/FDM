import pytest

@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """Permite acceso a BD en TODOS los tests sin tener que marcar @pytest.mark.django_db."""
    pass
