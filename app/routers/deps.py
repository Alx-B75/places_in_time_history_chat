"""
Router-level dependencies for request parsing and validation.
"""
from fastapi import Depends, HTTPException, Request
from app.schemas import Credentials


async def get_credentials(request: Request) -> Credentials:
    """
    Extracts credentials from JSON or form data and validates them into a Credentials model.
    """
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        data = await request.json()
        if not isinstance(data, dict) or "username" not in data or "password" not in data:
            raise HTTPException(status_code=422, detail="Username and password required")
        return Credentials(username=data["username"], password=data["password"])
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
        if not username or not password:
            raise HTTPException(status_code=422, detail="Username and password required")
        return Credentials(username=username, password=password)
    raise HTTPException(status_code=415, detail="Unsupported Media Type")
