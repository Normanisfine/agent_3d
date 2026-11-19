"""Bounded subprocesses; kill descendant jobs on timeout, not just their parent."""
import os
import signal
import subprocess


def run_process(command, *, timeout, input=None, **kwargs):
    with subprocess.Popen(command, start_new_session=True,
                          stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
                          **kwargs) as process:
        try:
            stdout, stderr = process.communicate(input=input, timeout=timeout)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
