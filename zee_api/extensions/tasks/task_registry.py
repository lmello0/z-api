import importlib
import inspect
import logging
import pkgutil
from pathlib import Path
from types import ModuleType
from typing import Any, Optional, Type

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from zee_api.core.extension_manager.base_extension import BaseExtension
from zee_api.core.zee_api import ZeeApi
from zee_api.extensions.tasks.settings import TaskModuleSettings
from zee_api.extensions.tasks.task import Task

logger = logging.getLogger(__name__)


class TaskRegistry(BaseExtension):
    """
    TaskRegistry is responsible for managing and scheduling tasks within the application.

    Attributes:
        _tasks (dict[str, Type[Task]]): A dictionary mapping task names to their respective Task classes.
        _scheduler (AsyncIOScheduler): The scheduler instance used to manage task execution.

    Methods:
        discover_tasks(tasks_package: str) -> None:
            Discovers and registers tasks from the specified package.

        setup_all_tasks() -> None:
            Sets up all registered tasks by adding them to the scheduler.

        start_scheduler() -> None:
            Starts the scheduler if it is not already running.

        shutdown_scheduler() -> None:
            Shuts down the scheduler if it is currently running.

    Functions:
        get_task_registry() -> TaskRegistry:
            Returns a singleton instance of TaskRegistry.
    """

    def __init__(self, app: ZeeApi):
        super().__init__(app)

        self._tasks: dict[str, Type[Task]] = {}
        self._scheduler: Optional[AsyncIOScheduler] = None
        self.config: Optional[TaskModuleSettings] = None

    async def init(self, config: dict[str, Any]) -> None:
        """Initialize task module"""
        self.config = TaskModuleSettings(**config)

        self._scheduler = AsyncIOScheduler()
        self._discover_tasks(self.config.task_package)
        self._setup_all_tasks()

        self._scheduler.start()

    async def cleanup(self) -> None:
        if self._scheduler:
            logger.info("Shutting down tasks module...")
            self._scheduler.shutdown(False)

            self._scheduler = None
            self._tasks.clear()

    def _discover_tasks(self, tasks_package: str) -> None:
        """
        Discovers and registers tasks from the specified package.

        Args:
            tasks_package (str): The name of the package to discover tasks from.

        Raises:
            ImportError: If the specified package cannot be imported.
            AttributeError: If a task class cannot be registered.
        """
        package: Optional[ModuleType] = None

        try:
            package = importlib.import_module(tasks_package)
        except ImportError:
            logger.warning(f"No module named {tasks_package}")
            return

        if package and hasattr(package, "__path__"):
            package_path = package.__path__
        else:
            package_path = [str(Path(package.__file__).parent)]  # type: ignore[arg-type]

        for _, modname, _ in pkgutil.walk_packages(
            path=package_path, prefix=tasks_package + ".", onerror=lambda x: None
        ):
            try:
                module = importlib.import_module(modname)

                for attr_name in dir(module):
                    attr = getattr(module, attr_name)

                    if (
                        inspect.isclass(attr)
                        and issubclass(attr, Task)
                        and attr is not Task
                        and attr.__module__ == modname
                    ):
                        self._tasks[attr.name] = attr

                        logger.info(f"Task registered: {attr.name}")
            except (ImportError, AttributeError):
                logger.warning(f"Failed to register task: {modname}")

    def _setup_all_tasks(self) -> None:
        """
        Sets up all registered tasks by adding them to the scheduler.

        This method iterates through all registered tasks, creates their instances,
        and schedules them using the scheduler instance.

        Logs:
            Info: When a task is successfully scheduled.
            Error: If a task fails to schedule.
        """
        for task_name, task_class in self._tasks.items():
            try:
                task_instance = task_class()

                if not self._scheduler:
                    raise ValueError("Scheduler is None")

                self._scheduler.add_job(
                    func=task_instance.execute, **task_instance.schedule
                )

                logger.info(
                    f"Task '{task_name}' scheduled with {task_instance.schedule}"
                )
            except Exception as e:
                logger.error(f"Failed to schedule task '{task_name}': {e}")
