import inspect
from abc import ABC, abstractmethod
from typing import Any, Coroutine, Optional, Union


class Task(ABC):
    """
    Base abstract class for tasks.

    Subclasses can implement execute() as either sync or async.
    Subclasses should define a 'name' and 'schedule' class attribute.
    """

    name: str
    schedule: dict

    def __init__(self, name: Optional[str] = None) -> None:
        """
        Initialize the task.

        Args:
            name: Optional name for the task
        """
        if not self.name and not name:
            self.name = name or self.__class__.__name__

    @abstractmethod
    def execute(
        self, *args: Any, **kwargs: Any
    ) -> Union[Any, Coroutine[Any, Any, Any]]:
        """
        Execute the task. Can be implement as sync or async

        Args:
            *args: Positional arguments for task execution
            **kwargs: Keyword arguments for task execution

        Returns:
            The result of task execution (or coroutine if async)
        """
        pass

    def is_async(self) -> bool:
        """
        Check if task is asynchronous.

        Returns:
            True if this task is asynchronous
        """
        return inspect.iscoroutine(self.execute)
