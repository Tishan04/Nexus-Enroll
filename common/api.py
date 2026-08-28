from fastapi import HTTPException

def raise_http(exc: Exception):
    raise HTTPException(500, str(exc)) from exc
