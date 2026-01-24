"""
Utilities for client unit and integration tests
"""

from collections.abc import Callable
from functools import wraps
from inspect import isawaitable, iscoroutinefunction, signature
from tempfile import NamedTemporaryFile
from time import monotonic_ns
from typing import Any

import pyinstrument
import pytest

from mountaineer.logging import LOGGER


def benchmark_function(  # noqa: C901, PLR0915
    max_time_seconds: float,
    time_budget_seconds: float = 5,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Wrap test functions in a timer that will enforce that the core logic completes
    in less than `max_time_seconds` seconds. Injects `start_timing` and `end_timing` into
    the function kwargs that will be called. Client callers should call these to scope
    where they want us to measure the core logic.

    :param time_budget_seconds: How many seconds we have to run benchmarking. This function will run
      at least 1 benchmark always, but the time budget allows users to better calibrate benchmark duration
      by taking the average of multiple runs.

    """

    def wrapper_fn(test_func: Callable[..., Any]) -> Callable[..., Any]:  # noqa: C901, PLR0915
        # We want to remove our custom functions from the signature, since pytest will natively
        # try to inject fixtures in this place
        orig_sig = signature(test_func)
        new_params = [p for name, p in orig_sig.parameters.items() if name not in {"start_timing", "end_timing"}]
        new_sig = orig_sig.replace(parameters=new_params)

        # Make sure that our function is a coroutine (if it is we assume user has decorated it with
        # pytest.mark.asyncio), otherwise we should raise an error because pytest won't know how
        # to run it
        if not iscoroutinefunction(test_func):
            msg = (
                f"Test function {test_func.__name__} is not a coroutine function. "
                "Please decorate it with pytest.mark.asyncio"
            )
            raise TypeError(msg)

        async def single_time_test(
            fn: Callable[..., Any],
            *args: Any,  # noqa: ANN401
            **kwargs: Any,  # noqa: ANN401
        ) -> tuple[int, int, Any]:
            # Try to run the test function regularly, and time it
            # Instrumenting profilers typically will slow down execution time so we want
            # to take time of the raw, non-instrumented function for benchmarking
            start: int | None = None
            end: int | None = None

            def start_timing() -> None:
                nonlocal start
                start = monotonic_ns()

            def end_timing() -> None:
                nonlocal end
                end = monotonic_ns()

            result = fn(
                *args,
                **kwargs,
                start_timing=start_timing,
                end_timing=end_timing,
            )
            if isawaitable(result):
                result = await result

            return (start, end, result)

        def validate_timing_result(start: int | None, end: int | None) -> None:
            """Validate that timing callbacks were called."""
            if start is None:
                msg = "Test function did not call start_timing"
                raise RuntimeError(msg)
            if end is None:
                msg = "Test function did not call end_timing"
                raise RuntimeError(msg)

        def validate_duration(duration: float) -> None:
            """Validate that execution duration is within limits."""
            if duration / 1e9 > max_time_seconds:
                msg = f"Test execution took {duration / 1e9}s, exceeding max of {max_time_seconds}s"
                raise RuntimeError(msg)

        @wraps(test_func)
        async def wrapper(
            *args: Any,  # noqa: ANN401
            **kwargs: Any,  # noqa: ANN401
        ) -> Any:  # noqa: ANN401
            bound = new_sig.bind(*args, **kwargs)
            bound.apply_defaults()

            average_duration: float | None = None

            try:
                timed_durations: list[tuple[int, int]] = []
                results: list[Any] = []
                global_start = monotonic_ns()

                # Run at least one test, but keep running until we hit our time budget
                while monotonic_ns() - global_start < time_budget_seconds * 1e9 or len(results) == 0:
                    start, end, result = await single_time_test(
                        test_func,
                        *args,
                        **kwargs,
                    )

                    validate_timing_result(start, end)
                    timed_durations.append((start, end))
                    results.append(result)

                average_duration = sum((end - start) for start, end in timed_durations) / len(timed_durations)

                LOGGER.info(
                    f"Collected {len(results)} timed durations in {(monotonic_ns() - global_start) / 1e9}",
                )
                LOGGER.info(f"Test function took average: {average_duration / 1e9}")

                validate_duration(average_duration)

                return results[0]

            except RuntimeError as e:
                LOGGER.error(f"Test function failed due to: {e}")

                # This should already be true, but we want to be explicit to help mypy
                assert average_duration is not None  # noqa: S101

                profiler = pyinstrument.Profiler()
                output_filename: str | None = None

                def start_timing() -> None:
                    nonlocal profiler
                    profiler.start()

                def end_timing() -> None:
                    nonlocal profiler
                    nonlocal output_filename
                    profiler.stop()
                    with NamedTemporaryFile(delete=False, suffix=".html") as file:
                        file.write(profiler.output_html().encode())
                    LOGGER.warning(f"PyInstrument profile saved at: {file.name}")
                    output_filename = file.name

                result = test_func(
                    *args,
                    **kwargs,
                    start_timing=start_timing,
                    end_timing=end_timing,
                )
                if isawaitable(result):
                    await result

                pytest.fail(
                    f"Test function failed in {average_duration / 1e9}s and profiles generated; "
                    f"Pyinstrument: {output_filename}",
                )

        wrapper.__signature__ = new_sig  # ty: ignore[attr-defined]
        return wrapper

    return wrapper_fn
