"""UniMatch FastAPI application package."""
__all__ = ["app", "create_app"]


def __getattr__(name):
    """Expose active rebuild/assistant app factories without importing retired V1 modules."""
    if name in __all__:
        from . import rebuild_assistant_api
        return getattr(rebuild_assistant_api, name)
    raise AttributeError(name)
