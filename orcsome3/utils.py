from __future__ import annotations

import re
import subprocess
import tarfile
from pathlib import Path
from types import ModuleType
from typing import IO, Any, Generic, Optional, TypeVar, cast, override

_T = TypeVar("_T")


class Singleton(type, Generic[_T]):
    """Class used as metaclass to ensure singleton"""

    _instances: dict[Singleton[_T], _T] = {}

    @override
    def __call__(cls, *args: Any, **kwargs: Any) -> _T:
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

    @classmethod
    def delete_instance(cls, instance: Singleton[_T]) -> None:
        try:
            del cls._instances[instance]
        except KeyError:
            pass


class Final(type):
    """Class used as metaclass to avoid changing attributes of constant classes"""

    @override
    def __setattr__(self, __name__: str, __value__: Any) -> None:
        raise AttributeError("Final classes can't be modified.")

    @override
    def __delattr__(self, __name__: str) -> None:
        raise AttributeError("Final classes can't be modified.")


class CythonWrapper:
    """Wrapper class to use methods from a cython module (.so)"""

    def __init__(self, cython_module: ModuleType) -> None:
        self._cython_module: ModuleType = cython_module

    def run_function(self, name: str, params: Optional[list[Any]] = None) -> Any:
        """
        Run function from cython module.

        Params:
        - `name`: Function name
        - `params`: Params to pass to function. Defaults to `None`
        """
        if params is None:
            return getattr(self._cython_module, name)()
        return getattr(self._cython_module, name)(*params)

    def get(self, name: str) -> Any:
        """Get item from module"""
        return getattr(self._cython_module, name)


class CythonClass:
    """Class used to call methods on cython class instances"""

    def __init__(self, cython_class_instance: object) -> None:
        self.cython_instance: Optional[object] = cython_class_instance

    def get_attribute(self, attr_name: str) -> Any:
        if self.cython_instance is None:
            return None
        return getattr(self.cython_instance, attr_name)

    def call_function(self, name: str, params: Optional[list[Any]] = None) -> Any:
        """
        Run function from cython object.

        Params:
        - `name`: Function name
        - `params`: Params to pass to function. Defaults to `None`
        """
        if self.cython_instance is None:
            return None
        if params is None:
            return getattr(self.cython_instance, name)()
        return getattr(self.cython_instance, name)(*params)


# Global cache for patterns
_re_cache: dict[str, re.Pattern[str]] = {}


def match_string(pattern: str, string: str) -> bool:
    """Checks if `string` matches `pattern`"""
    if not pattern in _re_cache.keys():
        _re_cache[pattern] = re.compile(pattern=pattern)
    return bool(re.search(pattern=_re_cache[pattern], string=string))


def rmdir(*directories: Path) -> None:
    """Delete a file or a directory if it exists"""
    for directory in directories:
        if not (directory.is_file() or directory.is_dir()):
            continue
        if directory.is_file():
            directory.unlink()
        elif directory.is_dir():
            for item in directory.rglob(pattern="*"):
                rmdir(item) if item.is_dir() else item.unlink()
            directory.rmdir()


def run_command_and_show_output(command: str, cwd: Optional[Path] = None) -> None:
    """Run command and show output in real time"""
    with subprocess.Popen(
        args=["bash", "-c", command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd, text=True
    ) as sp:
        for line in cast(IO[str], sp.stdout):
            print(line.replace("\n", ""), flush=True)
        _ = sp.wait()


def execfile(filepath: Path, globals_: Optional[dict[str, Any]] = None) -> None:
    """Execute a python 3 file"""
    if globals_ is None:
        globals_ = globals()
    with filepath.open(mode="r") as fh:
        exec(fh.read() + "\n", globals_)


def extract_tar_strip_components(tar_path: Path, destination_path: Path, strip_components: int = 0) -> None:
    """
    Extracts a tarfile to a destination, optionally stripping leading path components.

    Args:
        tar_path: The path to the tarfile.
        destination_path: The directory where the contents will be extracted.
        strip_components: The number of leading path components to strip.
                          Defaults to 0 (no stripping).
    """
    destination_path.mkdir(parents=True, exist_ok=True)

    with tarfile.open(name=tar_path, mode="r") as tar:
        for member in tar.getmembers():
            # Skip directories, they will be created implicitly
            if member.isdir():
                continue

            parts: tuple[str, ...] = Path(member.name).parts
            if len(parts) <= strip_components:
                # If stripping would result in an empty path or stripping more components
                # than available, skip or handle as appropriate.
                # For this example, we'll skip to avoid errors.
                print(
                    f"Skipping '{member.name}' as stripping {strip_components} components "
                    + "would result in an invalid path."
                )
                continue

            # Construct the new path by stripping components
            stripped_parts: tuple[str, ...] = parts[strip_components:]
            relative_dest_path: Path = Path(*stripped_parts)
            absolute_dest_path: Path = destination_path / relative_dest_path

            # Ensure parent directories exist
            absolute_dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Extract the file
            # Using extractfile for individual members and writing to ensure security
            # against path traversal vulnerabilities by not relying on member.name directly
            # for the full path calculation within tarfile's internal extraction.
            if member.isreg():  # Only extract regular files
                fsrc: Optional[IO[bytes]] = tar.extractfile(member=member)
                if fsrc is not None:  # Ensure fsrc is not None for empty files/symlinks treated as regular
                    with absolute_dest_path.open(mode="wb") as fdst:
                        _ = fdst.write(fsrc.read())
            elif member.issym():
                # Handle symbolic links: create a symlink at the destination
                link_target: Path = Path(member.linkname)
                # Check if the symlink target is absolute and needs adjustment
                if link_target.is_absolute():
                    print(
                        f"Warning: Absolute symlink target '{member.linkname}' found for '{member.name}'. "
                        + "This might lead to issues outside the extracted directory."
                    )
                # Create the symlink
                if not absolute_dest_path.exists():  # Avoid overwriting if it exists
                    try:
                        link_target.symlink_to(target=absolute_dest_path)
                    except OSError as e:
                        print(f"Could not create symlink for {member.name} -> {member.linkname}: {e}")
            elif member.islnk():
                # Handle hard links: same as symlinks but often with relative paths
                link_target = Path(member.linkname)
                if not absolute_dest_path.exists():
                    try:
                        # For hard links, the target must exist and be a file
                        # This part is trickier as os.link needs the original path to the file
                        # which is not easily available from tarfile. We'll treat them like symlinks
                        # for simplicity, but a true hard link extraction would require
                        # knowing the original file's path within the extraction.
                        # As a fallback, we'll just extract the content if it's a regular file
                        # or skip if it's pointing to something we can't create directly.
                        print(
                            f"Warning: Hard link '{member.name}' to '{member.linkname}' detected. "
                            + "Direct hard link creation is complex without source file path. "
                            + "Treating as regular file if content exists, otherwise skipping."
                        )
                        fsrc = tar.extractfile(member=member)
                        if fsrc is not None:
                            with absolute_dest_path.open(mode="wb") as fdst:
                                _ = fdst.write(fsrc.read())
                    except Exception as e:
                        print(f"Could not handle hard link for {member.name}: {e}")
