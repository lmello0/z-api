from importlib.metadata import entry_points
from typing import Protocol

from fastapi import FastAPI

from z_api.core.config.settings import Settings


class Plugin(Protocol):
    name: str

    def enabled(self, settings: Settings) -> bool: ...

    def setup(self, app: FastAPI, settings: Settings) -> None: ...

    async def on_shutdown(self, app: FastAPI) -> None: ...


def load_plugins(group: str = "z_api.extensions") -> list[Plugin]:
    plugs: list[Plugin] = []

    for ep in entry_points().select(group=group):
        plugin_factory = ep.load()
        plugin = plugin_factory() if callable(plugin_factory) else plugin_factory
        plugs.append(plugin)

    return plugs


def activate_plugins(app: FastAPI, settings: Settings) -> list[Plugin]:
    active: list[Plugin] = []

    for p in load_plugins():
        if p.enabled(settings):
            p.setup(app, settings)
            active.append(p)

    return active
 