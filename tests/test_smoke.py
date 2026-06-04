# tests/test_smoke.py
import tessera


def test_package_imports():
    assert tessera.__version__ == "0.1.0"
