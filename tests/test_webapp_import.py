from src.webapp import app


def test_webapp_importable() -> None:
    assert hasattr(app, "main")
    assert callable(app.main)
