"""Experimental HTTPS inference API for #24; HTTP stays outside sonar_vision.

Only `app` and `__main__` import FastAPI/uvicorn. The remaining modules use the
standard library (plus python-multipart for parsing) so their logic is testable
without the optional `api` extra.
"""
