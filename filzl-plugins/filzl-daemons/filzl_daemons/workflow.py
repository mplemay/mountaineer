# Support generic Queue[Obj] syntax
from __future__ import annotations

import asyncio
import multiprocessing
from abc import ABC, ABCMeta, abstractmethod
from datetime import datetime, timedelta, timezone
from itertools import chain
from multiprocessing.managers import SyncManager
from traceback import format_exc
from typing import Awaitable, Generic, Type, TypeVar, get_args, get_origin
from uuid import UUID

from filzl.logging import LOGGER
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from filzl_daemons.actions import ActionExecutionStub
from filzl_daemons.db import PostgresBackend
from filzl_daemons.io import AsyncMultiprocessingQueue, safe_task
from filzl_daemons.models import QueableStatus
from filzl_daemons.registry import REGISTRY
from filzl_daemons.retry import RetryPolicy
from filzl_daemons.state import init_state, update_state
from filzl_daemons.tasks import TaskManager
from filzl_daemons.timeouts import TimeoutDefinition, TimeoutMeasureType, TimeoutType
from filzl_daemons.workers.action import ActionWorkerProcess, TaskDefinition
from filzl_daemons.workers.instance import InstanceTaskDefinition, InstanceWorkerProcess

T = TypeVar("T", bound=BaseModel)
K = TypeVar("K", bound=BaseModel)


class TaskException(Exception):
    pass


class WorkflowInstance(Generic[T]):
    def __init__(
        self,
        *,
        input_payload: T,
        instance_id: int,
        instance_queue: str,
        task_manager: TaskManager,
        instance_process_id: UUID,
    ):
        self.input_payload = input_payload
        self.instance_id = instance_id
        self.instance_queue = instance_queue
        self.task_manager = task_manager
        self.instance_process_id = instance_process_id

        self.state = init_state(input_payload)

    async def run_action(
        self,
        action: Awaitable[K],
        *,
        retry: RetryPolicy,
        timeouts: list[TimeoutDefinition] | None = None,
        max_retries: int = 0,
    ) -> K:
        """
        Main entry point for running an action in the workflow. All calls should
        flow through your instance's run_action method.

        This method allows us to inject instance-specific metadata into
        the action.

        """
        # Execute the awaitable. If we receive a execution stub, we should queue it in
        # the backend
        result = await action

        if isinstance(result, ActionExecutionStub):
            new_state = update_state(self.state, result)
            self.state = new_state

            # Queue the action
            wait_future = await self.task_manager.queue_work(
                task=result,
                instance_id=self.instance_id,
                queue_name=self.instance_queue,
                state=new_state,
                retry=retry,
                instance_process_id=self.instance_process_id,
            )
            result = await wait_future
        else:
            raise ValueError(
                f"Actions must be wrapped in @action, incorrect future: {action}"
            )

        return result


class WorkflowMeta(ABCMeta):
    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        REGISTRY.register_workflow(cls)  # type: ignore

        input_model: Type[BaseModel] | None = None
        output_model: Type[BaseModel] | None = None

        # We should only validate Workflow subclasses, not the Workflow class itself
        if cls.__name__ == "Workflow":
            return

        # Attempt to sniff the generic type for input_model
        for base in cls.__orig_bases__:  # type: ignore
            if (
                get_origin(base)
                and get_origin(base).__name__ == "Workflow"
                and get_args(base)
            ):
                # Make sure it's a BaseModel
                if not issubclass(get_args(base)[0], BaseModel):
                    raise TypeError(
                        f"Workflow `{cls.__name__}` must have a BaseModel as its generic type"
                    )
                input_model = get_args(base)[0]
                break

        # Sniff the run() method for its return value
        if "run" in dct:
            run_method = dct["run"]
            if not callable(run_method):
                raise TypeError(f"Workflow `{cls.__name__}` must have a run() method")
            output_model = run_method.__annotations__.get("return")

            if output_model and not issubclass(output_model, BaseModel):
                raise TypeError(
                    f"Workflow `{cls.__name__}` must have a BaseModel as its return type annotation"
                )

        if input_model is None:
            raise TypeError(
                f"Workflow `{cls.__name__}` must have a generic type annotation"
            )
        if output_model is None:
            raise TypeError(
                f"Workflow `{cls.__name__}` run() must have a return type annotation"
            )

        cls.input_model = input_model
        cls.output_model = output_model


class DaemonResponseFuture:
    def __init__(self, instance_id: int, *, backend: PostgresBackend):
        self.instance_id = instance_id
        self.backend = backend

    async def wait(self):
        """
        Performs a polling-based wait for the result of the workflow instance. Either returns
        the result or raises a TaskException if the workflow failed.

        TODO: Refactor to use notifications instead of polling

        """
        while True:
            async with self.backend.get_object_by_id(
                self.backend.local_models.DaemonWorkflowInstance,
                self.instance_id,
            ) as (instance, session):
                if instance.end_time:
                    workflow_cls = REGISTRY.get_workflow(instance.registry_id)

                    if instance.result_body is not None:
                        return workflow_cls.output_model.model_validate_json(
                            instance.result_body
                        )
                    else:
                        raise TaskException(
                            f"Workflow failed: {instance.exception}: {instance.exception_stack}"
                        )

            await asyncio.sleep(1)


class Workflow(ABC, Generic[T], metaclass=WorkflowMeta):
    input_model: Type[T]
    output_model: Type[BaseModel]

    def __init__(self, backend: PostgresBackend):
        self.backend = backend

    @abstractmethod
    async def run(self, instance: WorkflowInstance[T]) -> BaseModel:
        pass

    async def run_handler(
        self,
        instance_id: int,
        instance_queue: str,
        raw_input: str,
        task_manager: TaskManager,
        instance_process_id: UUID,
    ):
        try:
            input_payload = self.input_model.model_validate_json(raw_input)

            # Call the client workflow logic
            result = await self.run(
                WorkflowInstance(
                    input_payload=input_payload,
                    instance_id=instance_id,
                    instance_queue=instance_queue,
                    task_manager=task_manager,
                    instance_process_id=instance_process_id,
                )
            )

            async with self.backend.get_object_by_id(
                self.backend.local_models.DaemonWorkflowInstance,
                instance_id,
            ) as (instance, session):
                instance.status = QueableStatus.DONE
                instance.result_body = result.model_dump_json()
                instance.end_time = datetime.now(timezone.utc)
                await session.commit()
        except Exception as e:
            LOGGER.exception(f"Workflow `{self.__class__.__name__}` failed due to: {e}")

            async with self.backend.get_object_by_id(
                self.backend.local_models.DaemonWorkflowInstance,
                instance_id,
            ) as (instance, session):
                instance.status = QueableStatus.DONE
                instance.exception = str(e)
                instance.exception_stack = format_exc()
                await session.commit()

    async def queue_task(self, task_input: T):
        async with self.backend.session_maker() as session:
            db_instance = self.backend.local_models.DaemonWorkflowInstance(
                workflow_name=self.__class__.__name__,
                registry_id=REGISTRY.get_registry_id_for_workflow(self.__class__),
                input_body=task_input.model_dump_json(),
                launch_time=datetime.now(timezone.utc),
            )

            session.add(db_instance)
            await session.commit()

        if db_instance.id is None:
            raise ValueError("Failed to get ID for new workflow instance")

        return DaemonResponseFuture(
            db_instance.id,
            backend=self.backend,
        )


class DaemonClient:
    """
    Interacts with a remote daemon pool from client code.

    """

    def __init__(
        self,
        backend: PostgresBackend,
    ):
        """
        Workflows only need to be provided if the daemon becomes a runner
        """
        self.backend = backend
        self.workflows: dict[Type[Workflow], Workflow] = {}

    async def queue_new(self, workflow: Type[Workflow[T]], payload: T):
        """
        Client callers should call this method to queue a new task

        """
        if workflow not in self.workflows:
            self.workflows[workflow] = workflow(
                backend=self.backend,
            )
        return await self.workflows[workflow].queue_task(payload)


class DaemonRunner:
    """
    Runs the daemon in the current container / machine. Supports multiple workflows
    running in one DaemonRunner.

    """

    def __init__(
        self,
        backend: PostgresBackend,
        workflows: list[Type[Workflow[T]]],
        max_workers: int | None = None,
        threads_per_worker: int = 1,
        max_instance_workers: int = 1,
        max_instances_per_worker: int = 1000,
        update_scheduled_refresh: int = 30,
        update_timed_out_workers_refresh: int = 30,
    ):
        """
        :param max_workers: If None, we'll use the number of CPUs on the machine
        :param threads_per_worker: The number of threads to use per worker. If you have
            heavily CPU-bound tasks, keeping the default of 1 task per process is probably
            good. Otherwise in the case of more I/O bound tasks, you might want to increase
            this number.
        :param update_scheduled_refresh: Seconds between bringing the scheduled task queue
            into the main queue.
        :param update_timed_out_workers_refresh: Seconds between checking for timed out
            workers and requeuing their items.

        """
        self.backend = backend
        self.workflows = workflows

        self.max_workers = max_workers or multiprocessing.cpu_count()
        self.threads_per_worker = threads_per_worker
        self.max_instance_workers = max_instance_workers
        self.max_instances_per_worker = max_instances_per_worker

        self.update_scheduled_refresh = update_scheduled_refresh
        self.update_timed_out_workers_refresh = update_timed_out_workers_refresh

    def run(self, workflows):
        """
        Runs the selected workflows / actions.

        """
        with multiprocessing.Manager() as manager:
            asyncio.run(self.handle_jobs(manager))

    async def handle_jobs(self, multiprocessing_manager: SyncManager):
        """
        Main task execution entrypoint. Takes care of:
            - Setting up isolated worker processes, one per CPU
            - Healthcheck those isolated worker processes, replace the ones that have issues
            - Iterate through the instance queue and add the ready workflows to the current
                async loop for execution
            - Iterate through the action queue and assign work to the workers

        """
        # Spawn our worker processes
        worker_processes: dict[UUID, ActionWorkerProcess] = {}
        instance_worker_processes: dict[UUID, InstanceWorkerProcess] = {}
        already_drained: set[UUID] = set()

        # Workers only handle actions, so we set up a queue to route all the collected
        # actions in the format that the workers expect
        worker_queue: multiprocessing.Queue[TaskDefinition] = multiprocessing.Queue(
            maxsize=self.max_workers * self.threads_per_worker
        )
        instance_queue: AsyncMultiprocessingQueue[
            InstanceTaskDefinition
        ] = AsyncMultiprocessingQueue(
            maxsize=self.max_instance_workers * self.max_instances_per_worker
        )

        task_manager = TaskManager(self.backend, manager=multiprocessing_manager)

        async def start_new_worker():
            # Start a new worker to replace the one that's draining
            process = ActionWorkerProcess(
                worker_queue, self.backend, pool_size=self.threads_per_worker
            )
            await process.start()

            # Make sure to do after the process is started
            process.add_is_draining_callback(is_draining_callback)

            worker_processes[process.process_id] = process

            return process

        async def start_new_instance_worker():
            process = InstanceWorkerProcess(
                instance_queue,
                self.backend,
                pool_size=self.max_instances_per_worker,
                task_manager=task_manager,
            )
            task_manager.worker_register(process.process_id)

            await process.start()
            instance_worker_processes[process.process_id] = process

            return process

        async def is_draining_callback(worker: ActionWorkerProcess):
            # If we're alerted that the process is draining, we should
            # start a new one. Also handle the case where processes quit
            # without a draining signal.
            if worker.process_id in already_drained:
                return
            already_drained.add(worker.process_id)

            await start_new_worker()

        async def health_check():
            while True:
                LOGGER.debug("Running health check")
                # If the process has been terminated without a draining signal,
                # we should start a new one
                for process_id, worker_process in list(worker_processes.items()):
                    # Handle potential terminations of the process for other reasons
                    if not worker_process.is_alive():
                        await is_draining_callback(worker_process)
                        del worker_processes[process_id]
                for process_id, instance_process in list(
                    instance_worker_processes.items()
                ):
                    if not instance_process.is_alive():
                        await start_new_instance_worker()
                        del instance_worker_processes[process_id]

                await asyncio.sleep(5)

        # Initial worker process bootstrap for action handlers
        for _ in range(self.max_workers):
            process = await start_new_worker()
            LOGGER.debug(f"Spawned: {process.process_id}")

        for _ in range(self.max_instance_workers):
            process = await start_new_instance_worker()
            LOGGER.debug(f"Spawned: {process.process_id}")

        # Infinitely blocking
        try:
            await asyncio.gather(
                # Bulk execute the instance behavior in this main process, for now
                safe_task(self.queue_instance_work)(instance_queue),
                # We will consume database actions here and delegate to our other processes
                safe_task(self.queue_action_work)(worker_queue),
                # Update the DB-level actions that are now ready to be re-queued
                safe_task(self.update_scheduled_actions)(),
                # Update the DB-level actions/instance values if their workers have timed out
                # Workers themselves will handle the requeue of the actions if they time out within
                # the active runloop
                safe_task(self.update_timed_out_workers)(),
                # Required to wake up our sleeping instance workers
                # when we are done processing an action
                safe_task(task_manager.main_delegate_done_actions)(),
                # Determine the health of our worker processes
                safe_task(health_check)(),
            )
        except asyncio.CancelledError:
            LOGGER.debug(
                f"DaemonRunner was cancelled, cleaning up {len(worker_processes)} worker processes"
            )
            for process in chain(
                worker_processes.values(), instance_worker_processes.values()
            ):
                process.terminate()
            for process in chain(
                worker_processes.values(), instance_worker_processes.values()
            ):
                process.join()
            LOGGER.debug("Worker processes cleaned up")

        LOGGER.debug("DaemonRunner finished")

    async def update_scheduled_actions(self):
        """
        Determine the actions that have been scheduled in the future and are now ready
        to be executed by the action workers.

        """
        while True:
            async with self.backend.session_maker() as session:
                result = await session.execute(
                    text(
                        f"UPDATE {self.backend.local_models.DaemonAction.__tablename__} SET status = :queued_status WHERE status = :scheduled_status AND schedule_after < now()"
                    ),
                    {
                        "queued_status": QueableStatus.QUEUED,
                        "scheduled_status": QueableStatus.SCHEDULED,
                    },
                )
                await session.commit()
                affected_rows = result.rowcount
                LOGGER.debug(f"Updated {affected_rows} scheduled rows")
            await asyncio.sleep(self.update_scheduled_refresh)

    async def update_timed_out_workers(self, worker_timeouts=5 * 60):
        """
        Determine the workers that have timed out and re-queue their actions
        and instances.

        """
        while True:
            await self._update_timed_out_workers_single(worker_timeouts)
            await asyncio.sleep(self.update_timed_out_workers_refresh)

    async def _update_timed_out_workers_single(self, worker_timeouts: int):
        async with self.backend.session_maker() as session:
            # Get all the workers that have timed out and haven't yet been cleaned up
            # We recognize that this can introduce a race condition, but because the actions here are idempotent
            # we can execute the SQL updates multiple times
            current_time = datetime.now(timezone.utc)
            timeout_threshold = current_time - timedelta(seconds=worker_timeouts)

            timed_out_workers_query = text(
                f"""
                SELECT id FROM {self.backend.local_models.WorkerStatus.__tablename__}
                WHERE last_ping < :timeout_threshold AND cleaned_up = FALSE
            """
            )
            timed_out_workers_result = await session.execute(
                timed_out_workers_query, {"timeout_threshold": timeout_threshold}
            )
            timed_out_worker_ids = [row[0] for row in timed_out_workers_result]

            if not timed_out_worker_ids:
                return

            # Right now we requeue action failures immediately if they happened because of a disconnected
            # worker, versus a worker that has timed out.
            result = await session.execute(
                text(
                    f"UPDATE {self.backend.local_models.DaemonAction.__tablename__} SET status = :new_status WHERE status = :old_status AND assigned_worker_status_id = ANY(:timed_out_worker_ids)"
                ),
                {
                    "new_status": QueableStatus.QUEUED,
                    "old_status": QueableStatus.IN_PROGRESS,
                    "timed_out_worker_ids": timed_out_worker_ids,
                },
            )
            await session.commit()
            affected_rows = result.rowcount
            LOGGER.debug(
                f"update_timed_out_workers: Updated {affected_rows} action rows"
            )

            # Run the same logic for the instance table
            result = await session.execute(
                text(
                    f"UPDATE {self.backend.local_models.DaemonWorkflowInstance.__tablename__} SET status = :new_status WHERE status = :old_status AND assigned_worker_status_id = ANY(:timed_out_worker_ids)"
                ),
                {
                    "new_status": QueableStatus.QUEUED,
                    "old_status": QueableStatus.IN_PROGRESS,
                    "timed_out_worker_ids": timed_out_worker_ids,
                },
            )
            affected_rows = result.rowcount
            LOGGER.debug(
                f"update_timed_out_workers: Updated {affected_rows} instance rows"
            )

            # Mark the workers as cleaned up
            cleanup_workers_query = text(
                f"""
                UPDATE {self.backend.local_models.WorkerStatus.__tablename__}
                SET cleaned_up = TRUE
                WHERE id = ANY(:timed_out_worker_ids)
            """
            )
            await session.execute(
                cleanup_workers_query, {"timed_out_worker_ids": timed_out_worker_ids}
            )

            await session.commit()

    async def queue_instance_work(
        self, instance_queue: AsyncMultiprocessingQueue[InstanceTaskDefinition]
    ):
        async for notification in self.backend.iter_ready_objects(
            model=self.backend.local_models.DaemonWorkflowInstance,
            queues=[],
        ):
            LOGGER.info(f"Instance queue should handle job: {notification}")

            has_exclusive = await self.get_exclusive_access(
                self.backend.local_models.DaemonWorkflowInstance, notification.id
            )
            if not has_exclusive:
                continue

            async with self.backend.get_object_by_id(
                self.backend.local_models.DaemonWorkflowInstance, notification.id
            ) as (instance_definition, _):
                pass

            if not instance_definition.id:
                continue

            # Queue up this instance for processing
            task = InstanceTaskDefinition(
                instance_id=instance_definition.id,
                registry_id=instance_definition.registry_id,
                queue_name=instance_definition.workflow_name,
                raw_input=instance_definition.input_body,
            )
            LOGGER.info(f"Queueing instance task: {task} {instance_definition}")

            await instance_queue.async_put(task)

    async def queue_action_work(
        self, worker_queue: multiprocessing.Queue[TaskDefinition]
    ):
        """
        Listen to database changes for actions that are now ready to be executed and place
        them into the multiprocess queue for the system wide workers.

        """
        async for notification in self.backend.iter_ready_objects(
            model=self.backend.local_models.DaemonAction,
            queues=[],
        ):
            LOGGER.info(f"Action queue should handle job: {notification}")

            has_exclusive = await self.get_exclusive_access(
                self.backend.local_models.DaemonAction, notification.id
            )
            if not has_exclusive:
                continue

            # Get the full object from the database
            async with self.backend.get_object_by_id(
                model=self.backend.local_models.DaemonAction,
                id=notification.id,
            ) as (action_definition, _):
                pass

            field_to_timeout = {
                "wall_soft_timeout": (TimeoutMeasureType.WALL_TIME, TimeoutType.SOFT),
                "wall_hard_timeout": (TimeoutMeasureType.WALL_TIME, TimeoutType.HARD),
                "cpu_soft_timeout": (TimeoutMeasureType.CPU_TIME, TimeoutType.SOFT),
                "cpu_hard_timeout": (TimeoutMeasureType.CPU_TIME, TimeoutType.HARD),
            }

            if not action_definition.id:
                LOGGER.error(
                    f"Action definition {action_definition} has no ID. Skipping."
                )
                continue

            task_definition = TaskDefinition(
                action_id=action_definition.id,
                registry_id=action_definition.registry_id,
                input_body=action_definition.input_body,
                timeouts=[
                    TimeoutDefinition(
                        measurement=measure,
                        timeout_type=timeout_type,
                        timeout_seconds=getattr(action_definition, timeout_key),
                    )
                    for timeout_key, (measure, timeout_type) in field_to_timeout.items()
                    if getattr(action_definition, timeout_key) is not None
                ],
            )
            LOGGER.info(f"Will queue: {task_definition} {action_definition}")

            worker_queue.put(task_definition)

    async def get_exclusive_access(self, model, id: int):
        has_exclusive_lock = True

        async with self.backend.session_maker() as session:
            try:
                async with session.begin():
                    # Attempt to lock the specific job by ID with NOWAIT
                    stmt = (
                        select(model).where(model.id == id).with_for_update(nowait=True)
                    )
                    result = await session.execute(stmt)
                    job = result.scalar_one_or_none()

                    if job:
                        job.status = QueableStatus.IN_PROGRESS
                        await session.commit()
                        has_exclusive_lock = True

            except SQLAlchemyError as e:
                # Handle the case where locking the job fails because it's already locked
                await session.rollback()
                LOGGER.debug(f"Failed to lock job {id}: {e}")

        return has_exclusive_lock