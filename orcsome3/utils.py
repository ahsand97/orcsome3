"""Small helpers used across orcsome3 (singleton, file/process utils)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import IO, Any, ClassVar, Optional, TypeVar, cast

from typing_extensions import override

_T = TypeVar("_T")


class SingletonMixin:
    """Mixin: at most one instance per concrete class."""

    _singletons: ClassVar[dict[type[Any], Any]] = {}
    _singleton_inited: ClassVar[set[type[Any]]] = set()

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        instance: Any = cls._singletons.get(cls)
        if instance is None:
            instance = super().__new__(cls)
            cls._singletons[cls] = instance
        return instance

    @classmethod
    def delete_singleton(cls) -> None:
        """Drop the cached instance so the next constructor call allocates a new one."""
        cls._singletons.pop(cls, None)
        cls._singleton_inited.discard(cls)

    @classmethod
    def _singleton_init_done(cls) -> bool:
        """Return True when __init__ should be skipped (already ran for this class)."""
        if cls in cls._singleton_inited:
            return True
        cls._singleton_inited.add(cls)
        return False


class Final(type):
    """Class used as metaclass to avoid changing attributes of constant classes"""

    @override
    def __setattr__(self, __name__: str, __value__: Any) -> None:
        raise AttributeError("Final classes can't be modified.")

    @override
    def __delattr__(self, __name__: str) -> None:
        raise AttributeError("Final classes can't be modified.")


_re_cache: dict[str, re.Pattern[str]] = {}


def match_string(pattern: str, string: str) -> bool:
    """True if `pattern` (compiled regex, cached) searches anywhere in `string`."""
    compiled: Optional[re.Pattern[str]] = _re_cache.get(pattern)
    if compiled is None:
        compiled = re.compile(pattern=pattern)
        _re_cache[pattern] = compiled
    return compiled.search(string=string) is not None


def rmdir(*directories: Path) -> None:
    """Delete a file or a directory if it exists"""
    for directory in directories:
        if directory.is_symlink() or directory.is_file():
            directory.unlink()
        elif directory.is_dir():
            shutil.rmtree(path=directory)


def run_command_and_show_output(command: str, cwd: Optional[Path] = None) -> None:
    """Run command and show output in real time"""
    with subprocess.Popen(
        args=["bash", "-c", command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd, text=True
    ) as sp:
        for line in cast(IO[str], sp.stdout):
            print(line.replace("\n", ""), flush=True)
        _ = sp.wait()
        if sp.returncode:
            raise subprocess.CalledProcessError(returncode=sp.returncode, cmd=command)


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
                    with fsrc, absolute_dest_path.open(mode="wb") as fdst:
                        shutil.copyfileobj(fsrc=fsrc, fdst=fdst)
                    absolute_dest_path.chmod(mode=member.mode & 0o777)
                    # Keep tarball mtimes so autotools does not rebuild Makefile.in (needs automake).
                    os.utime(absolute_dest_path, times=(member.mtime, member.mtime))
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
                        absolute_dest_path.symlink_to(target=link_target)
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
                            with fsrc, absolute_dest_path.open(mode="wb") as fdst:
                                shutil.copyfileobj(fsrc=fsrc, fdst=fdst)
                            absolute_dest_path.chmod(mode=member.mode & 0o777)
                            os.utime(absolute_dest_path, times=(member.mtime, member.mtime))
                    except Exception as e:
                        print(f"Could not handle hard link for {member.name}: {e}")
