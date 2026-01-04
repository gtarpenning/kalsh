from kalsh import __version__


def test_smoke_imports_package():
    assert isinstance(__version__, str)

