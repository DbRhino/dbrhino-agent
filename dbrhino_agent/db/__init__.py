from urllib.parse import urlparse


def create(*, connect_to, **kwargs):
    parsed = urlparse(connect_to)
    if parsed.scheme == "postgresql":
        from .postgresql import Postgresql
        cls = Postgresql
    elif parsed.scheme == "mysql":
        from .mysql import MySQL
        cls = MySQL
    else:
        raise Exception("Unknown scheme: " + str(parsed.scheme))
    return cls(connect_to=connect_to, parsed_url=parsed, **kwargs)

__all__ = ["create"]
