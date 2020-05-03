import asyncio
import logging
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)


class EventSystem:
    __slots__ = ("__topics",)

    __topics: Dict[str, List[Callable]]

    def __init__(self) -> None:
        self.__topics = {}

    def add_listener(self, name: str, callback: Callable) -> None:
        try:
            listeners = self.__topics[name]
        except KeyError:
            listeners = self.__topics[name] = []

        listeners.append(callback)

    async def __dispatch_to(self, f: Callable, args, kwargs) -> None:
        try:
            await f(*args, **kwargs)
        except Exception:
            logger.exception("dispatch to %s failed", f)

    async def dispatch(self, name: str, *args, **kwargs) -> None:
        try:
            listeners = self.__topics[name]
        except KeyError:
            return

        await asyncio.gather(*(self.__dispatch_to(f, args, kwargs) for f in listeners))

    def dispatch_async(self, name: str, *args, **kwargs) -> asyncio.Task:
        return asyncio.create_task(self.dispatch(name, *args, **kwargs))
