"""
Import test for the FastAPI application.
"""
from fastapi import FastAPI


def test_import_app() -> None:
    """
    Imports the FastAPI application and asserts it is a FastAPI instance.
    """
    from app.main import app
    assert isinstance(app, FastAPI)
