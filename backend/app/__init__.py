__all__ = ["app", "create_app"]


def __getattr__(name):
    """Preserve legacy exports without importing legacy serving for additive apps."""
    if name in __all__:
        from . import main
        return getattr(main, name)
    raise AttributeError(name)

