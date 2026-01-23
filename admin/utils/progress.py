"""
Progress utilities for the Review Fraud Workshop.

Provides progress logging with tqdm for long-running operations,
including support for nested progress bars.
"""

from typing import Optional, Iterator, TypeVar, Iterable, Callable, Any
from contextlib import contextmanager

from tqdm import tqdm


T = TypeVar('T')


class ProgressLogger:
    """
    A progress logger using tqdm for long-running operations.

    Supports nested progress bars for complex operations like loading
    multiple files where each file has multiple records.

    Example:
        >>> # Simple usage
        >>> with ProgressLogger(total=100, desc="Processing") as progress:
        ...     for i in range(100):
        ...         # do work
        ...         progress.update(1)

        >>> # Nested progress bars
        >>> files = ["file1.json", "file2.json"]
        >>> with ProgressLogger(total=len(files), desc="Files") as outer:
        ...     for file in files:
        ...         records = load_file(file)
        ...         with outer.nested(total=len(records), desc=file) as inner:
        ...             for record in records:
        ...                 process(record)
        ...                 inner.update(1)
        ...         outer.update(1)
    """

    def __init__(
        self,
        total: Optional[int] = None,
        desc: Optional[str] = None,
        unit: str = "it",
        disable: bool = False,
        position: int = 0,
        leave: bool = True,
        ncols: Optional[int] = None,
        mininterval: float = 0.1,
        **kwargs
    ):
        """
        Initialize the progress logger.

        Args:
            total: Total number of iterations (None for unknown)
            desc: Description prefix for the progress bar
            unit: Unit of iteration (e.g., "files", "records", "docs")
            disable: If True, disable the progress bar entirely
            position: Position of the progress bar (0 = top, useful for nesting)
            leave: If True, leave the progress bar on screen after completion
            ncols: Width of the progress bar (None for auto)
            mininterval: Minimum update interval in seconds
            **kwargs: Additional arguments passed to tqdm
        """
        self.total = total
        self.desc = desc
        self.unit = unit
        self.disable = disable
        self.position = position
        self.leave = leave
        self.ncols = ncols
        self.mininterval = mininterval
        self.kwargs = kwargs
        self._pbar: Optional[tqdm] = None
        self._nested_position = 1

    def __enter__(self) -> "ProgressLogger":
        """Enter the context manager and create the progress bar."""
        self._pbar = tqdm(
            total=self.total,
            desc=self.desc,
            unit=self.unit,
            disable=self.disable,
            position=self.position,
            leave=self.leave,
            ncols=self.ncols,
            mininterval=self.mininterval,
            **self.kwargs
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context manager and close the progress bar."""
        if self._pbar is not None:
            self._pbar.close()
            self._pbar = None

    def update(self, n: int = 1) -> None:
        """
        Update the progress bar.

        Args:
            n: Number of iterations to advance
        """
        if self._pbar is not None:
            self._pbar.update(n)

    def set_description(self, desc: str) -> None:
        """
        Update the progress bar description.

        Args:
            desc: New description
        """
        if self._pbar is not None:
            self._pbar.set_description(desc)

    def set_postfix(self, **kwargs) -> None:
        """
        Update the postfix displayed after the progress bar.

        Args:
            **kwargs: Key-value pairs to display
        """
        if self._pbar is not None:
            self._pbar.set_postfix(**kwargs)

    def set_total(self, total: int) -> None:
        """
        Update the total count (useful when total is initially unknown).

        Args:
            total: New total count
        """
        if self._pbar is not None:
            self._pbar.total = total
            self._pbar.refresh()

    @contextmanager
    def nested(
        self,
        total: Optional[int] = None,
        desc: Optional[str] = None,
        unit: str = "it",
        leave: bool = False,
        **kwargs
    ) -> Iterator["ProgressLogger"]:
        """
        Create a nested progress bar.

        Args:
            total: Total for the nested bar
            desc: Description for the nested bar
            unit: Unit for the nested bar
            leave: Whether to leave the nested bar after completion
            **kwargs: Additional arguments for tqdm

        Yields:
            ProgressLogger: A nested progress logger

        Example:
            >>> with ProgressLogger(total=10, desc="Outer") as outer:
            ...     for i in range(10):
            ...         with outer.nested(total=100, desc=f"Inner {i}") as inner:
            ...             for j in range(100):
            ...                 inner.update(1)
            ...         outer.update(1)
        """
        nested_logger = ProgressLogger(
            total=total,
            desc=desc,
            unit=unit,
            disable=self.disable,
            position=self._nested_position,
            leave=leave,
            ncols=self.ncols,
            mininterval=self.mininterval,
            **kwargs
        )
        self._nested_position += 1
        try:
            with nested_logger as logger:
                yield logger
        finally:
            self._nested_position -= 1


def progress_iter(
    iterable: Iterable[T],
    total: Optional[int] = None,
    desc: Optional[str] = None,
    unit: str = "it",
    disable: bool = False,
    **kwargs
) -> Iterator[T]:
    """
    Wrap an iterable with a progress bar.

    This is a convenience function for simple iteration with progress.

    Args:
        iterable: The iterable to wrap
        total: Total number of items (inferred from len() if possible)
        desc: Description for the progress bar
        unit: Unit of iteration
        disable: If True, disable the progress bar
        **kwargs: Additional arguments for tqdm

    Yields:
        Items from the iterable

    Example:
        >>> for item in progress_iter(items, desc="Processing"):
        ...     process(item)
    """
    # Try to get total from iterable if not provided
    if total is None:
        try:
            total = len(iterable)  # type: ignore
        except TypeError:
            pass

    yield from tqdm(
        iterable,
        total=total,
        desc=desc,
        unit=unit,
        disable=disable,
        **kwargs
    )


def batch_progress(
    items: list[T],
    batch_size: int,
    desc: Optional[str] = None,
    unit: str = "batch",
    disable: bool = False,
    process_fn: Optional[Callable[[list[T]], Any]] = None,
    **kwargs
) -> Iterator[list[T]]:
    """
    Process items in batches with progress tracking.

    Args:
        items: List of items to process
        batch_size: Size of each batch
        desc: Description for the progress bar
        unit: Unit of iteration (default: "batch")
        disable: If True, disable the progress bar
        process_fn: Optional function to call on each batch
        **kwargs: Additional arguments for tqdm

    Yields:
        Batches of items

    Example:
        >>> for batch in batch_progress(records, batch_size=100, desc="Indexing"):
        ...     es.bulk(body=batch)
    """
    total_batches = (len(items) + batch_size - 1) // batch_size

    with tqdm(
        total=total_batches,
        desc=desc,
        unit=unit,
        disable=disable,
        **kwargs
    ) as pbar:
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            if process_fn:
                process_fn(batch)
            yield batch
            pbar.update(1)


class MultiFileProgress:
    """
    Progress tracker for processing multiple files.

    Provides both file-level and record-level progress tracking.

    Example:
        >>> files = ["data1.json", "data2.json"]
        >>> with MultiFileProgress(files) as progress:
        ...     for file in files:
        ...         records = load_file(file)
        ...         with progress.file_context(file, total_records=len(records)) as file_prog:
        ...             for record in records:
        ...                 process(record)
        ...                 file_prog.update(1)
    """

    def __init__(
        self,
        files: list[str],
        desc: str = "Files",
        disable: bool = False
    ):
        """
        Initialize multi-file progress tracker.

        Args:
            files: List of file paths to process
            desc: Description for the outer progress bar
            disable: If True, disable progress bars
        """
        self.files = files
        self.desc = desc
        self.disable = disable
        self._outer_pbar: Optional[tqdm] = None
        self._current_file: Optional[str] = None

    def __enter__(self) -> "MultiFileProgress":
        """Enter context and create outer progress bar."""
        self._outer_pbar = tqdm(
            total=len(self.files),
            desc=self.desc,
            unit="file",
            disable=self.disable,
            position=0,
            leave=True
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context and close progress bar."""
        if self._outer_pbar is not None:
            self._outer_pbar.close()
            self._outer_pbar = None

    @contextmanager
    def file_context(
        self,
        filename: str,
        total_records: Optional[int] = None,
        unit: str = "rec"
    ) -> Iterator[tqdm]:
        """
        Context manager for processing a single file.

        Args:
            filename: Name of the file being processed
            total_records: Total records in the file
            unit: Unit for record counting

        Yields:
            tqdm: Progress bar for the file's records
        """
        self._current_file = filename

        # Create inner progress bar for records
        inner_pbar = tqdm(
            total=total_records,
            desc=f"  {filename}",
            unit=unit,
            disable=self.disable,
            position=1,
            leave=False
        )

        try:
            yield inner_pbar
        finally:
            inner_pbar.close()
            # Update outer progress bar
            if self._outer_pbar is not None:
                self._outer_pbar.update(1)
            self._current_file = None
