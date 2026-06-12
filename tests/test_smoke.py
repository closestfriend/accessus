# tests/test_smoke.py
import accessus


def test_package_imports():
    assert accessus.__version__ == "0.1.0"
