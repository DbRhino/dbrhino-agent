def create(*, name, **dbconf):
    if dbconf["type"] in ["postgresql", "redshift"]:
        from .postgresql import Postgresql
        cls = Postgresql
    elif dbconf["type"] == "mysql":
        from .mysql import MySQL
        cls = MySQL
    else:
        raise Exception("Unknown type: " + dbconf["type"])
    return cls(name, dbconf)
