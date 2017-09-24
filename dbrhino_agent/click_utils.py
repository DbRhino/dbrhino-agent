import click
import json
from . import config


class _ConfigType(click.ParamType):
    name = "json_file"

    def convert(self, value, param, ctx):
        return config.Config.from_file(value)

_JSON_FILE = _ConfigType()
CONFIG = ("--config", "-c")
CONFIG_OPTS = dict(type=_JSON_FILE, required=True)
