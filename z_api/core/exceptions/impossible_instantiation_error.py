from typing import Optional


class ImpossibleInstantiationError(Exception):
    def __init__(self, clazz: str, e: Optional[Exception] = None):
        message = f"Is impossible to instantiate {clazz}"

        if e:
            message = f"{message} due to error: {e}"

        super().__init__(message)
