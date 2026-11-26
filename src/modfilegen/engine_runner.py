"""Run a model executable and collect its outputs, without a shell.

Each model used to be launched through its own ``*run.sh``. Those scripts
needed bash, GNU ``sed -i -z``, ``awk``, ``basename``, ``cp --`` and ``rm``,
none of which a plain Windows install provides, and they hid the engine path
inside the script where no Python configuration could reach it.

What they did lives here instead, with two deliberate properties:

* **Fewer processes.** A bash launch spawned bash, two ``awk``, one
  ``basename``, one ``sed`` and one ``cp`` per copied file: eight to eleven
  processes per simulation. Here the engine is the only process.
* **The USM directory is still removed off the critical path.** The scripts
  did ``(rm -rf "$USM_DIR" &)``; a single background thread does it here,
  joined at interpreter exit so nothing is left behind -- unlike the detached
  subshell, which a dying worker could orphan.

Engine stdout goes to the null device by default, as the scripts did with
``> /dev/null``. Capturing it instead would buffer every line STICS prints,
for no use.
"""

import atexit
import errno
import os
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

#: Windows' "%1 is not a valid Win32 application", the counterpart of ENOEXEC.
_WINDOWS_BAD_EXE_FORMAT = 193

__all__ = [
    "run_engine",
    "copy_output",
    "copy_outputs",
    "remove_tree",
    "remove_usm",
    "wait_for_removals",
]


def run_engine(
    executable,
    arguments=(),
    *,
    cwd,
    timeout=None,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.PIPE,
    check=True,
    text=True,
):
    """Run ``executable`` with ``cwd`` as working directory.

    ``cwd`` replaces the ``cd "$USM_DIR"`` the scripts did, which also means
    the process no longer changes the directory of anything else.

    Returns the ``CompletedProcess``. With ``check=True`` a non-zero exit
    raises ``subprocess.CalledProcessError``, and exceeding ``timeout``
    raises ``subprocess.TimeoutExpired``, as before.
    """
    command = [str(executable), *(str(argument) for argument in arguments)]
    options = dict(
        cwd=str(cwd),
        timeout=timeout,
        stdout=stdout,
        stderr=stderr,
        check=check,
        text=text,
    )
    try:
        return subprocess.run(command, **options)
    except OSError as error:
        if not _needs_an_interpreter(error):
            raise
        return subprocess.run(_through_the_shell(command), **options)


def _needs_an_interpreter(error):
    """Whether the OS refused to execute the file itself.

    DSSAT's own ``run_dssat`` wrapper is a one-line shell script with no
    shebang, so ``execve`` returns ``ENOEXEC``; bash used to paper over that
    by falling back to ``sh``. On Windows a ``.bat`` or ``.cmd`` wrapper fails
    the same way, with error 193.
    """
    return error.errno == errno.ENOEXEC or (
        getattr(error, "winerror", None) == _WINDOWS_BAD_EXE_FORMAT
    )


def _through_the_shell(command):
    """The same command, handed to the platform interpreter.

    This is the narrow fallback for a wrapper script, not a return to the
    shell: the normal path still execs the engine directly, and the
    interpreters used here ship with the OS, unlike bash and the GNU tools
    the ``*run.sh`` scripts needed.

    The program is resolved against PATH first. A direct exec looks a bare
    name up in PATH, but an interpreter would take it as a path relative to
    the USM directory and report "command not found".
    """
    program, *arguments = command
    program = shutil.which(program) or program
    if os.name == "nt":
        return [os.environ.get("COMSPEC", "cmd.exe"), "/c", program, *arguments]
    return ["/bin/sh", program, *arguments]


def copy_output(source_dir, name, destination_dir, new_name):
    """Copy one output file under a new name, if the engine produced it.

    Returns the destination path, or ``None`` when the file is absent -- the
    scripts tested ``[ -f ... ]`` the same way and simply skipped.
    """
    source = Path(source_dir) / name
    if not source.is_file():
        return None
    destination = Path(destination_dir) / new_name
    shutil.copy2(source, destination)
    return destination


def copy_outputs(source_dir, pattern, destination_dir, rename, first_only=False):
    """Copy every file matching ``pattern``, naming each one with ``rename``.

    ``rename`` takes the source ``Path`` and returns the destination file
    name. ``first_only`` keeps the single-file behaviour of the STICS v9
    script, which copied the first match and stopped.

    Matches are sorted, so ``first_only`` picks a stable file instead of
    whatever order the filesystem happens to return.
    """
    destination_dir = Path(destination_dir)
    copied = []
    for source in sorted(Path(source_dir).glob(pattern)):
        if not source.is_file():
            continue
        destination = destination_dir / rename(source)
        shutil.copy2(source, destination)
        copied.append(destination)
        if first_only:
            break
    return copied


def remove_tree(path, retries=5, delay=0.1):
    """Delete a directory tree, retrying while a file is still held.

    Windows refuses to unlink a file another handle still has open, which a
    just-finished engine, an editor or a virus scanner can cause; POSIX does
    not, so the retry only ever costs something where it is needed.

    Returns True when the tree is gone.
    """
    path = Path(path)
    for attempt in range(retries):
        try:
            shutil.rmtree(path)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            if attempt == retries - 1:
                return False
            time.sleep(delay * (attempt + 1))
    return False


_removal_pool = None
_removal_lock = threading.Lock()


def _pool():
    global _removal_pool
    if _removal_pool is None:
        with _removal_lock:
            if _removal_pool is None:
                pool = ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="usm-remove"
                )
                atexit.register(pool.shutdown, wait=True)
                _removal_pool = pool
    return _removal_pool


def remove_usm(path, background=True):
    """Delete a finished USM directory.

    One background thread per process keeps the deletion off the simulation
    loop, as ``(rm -rf &)`` did. ``background=False`` deletes synchronously
    and returns whether it succeeded.
    """
    if not background:
        return remove_tree(path)
    _pool().submit(remove_tree, path)
    return None


def wait_for_removals():
    """Block until the queued deletions are done. For tests, mainly."""
    global _removal_pool
    pool, _removal_pool = _removal_pool, None
    if pool is not None:
        pool.shutdown(wait=True)
