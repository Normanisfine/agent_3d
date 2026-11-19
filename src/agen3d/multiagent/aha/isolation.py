"""Fail-closed Blender execution. Only candidate output is writable/credentials absent."""
import os
import shutil
from pathlib import Path
from ..process import run_process


def command(blender, aha, candidate, script, request):
    bwrap = shutil.which('bwrap')
    if not bwrap:
        raise RuntimeError('bubblewrap is required to execute generated Blender programs')
    candidate = Path(candidate).resolve()
    # Hide home/workspace entirely; expose only binaries, AHA code/assets and task inputs.
    cmd = [bwrap, '--unshare-all', '--die-with-parent', '--new-session', '--clearenv',
           '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'HOME', '/tmp',
           '--setenv', 'PYTHONDONTWRITEBYTECODE', '1', '--proc', '/proc', '--dev', '/dev',
           '--tmpfs', '/tmp']
    for root in ('/usr', '/bin', '/lib', '/lib64'):
        if Path(root).exists():
            cmd += ['--ro-bind', root, root]
    for root in ('/etc/fonts', '/etc/ld.so.cache'):
        if Path(root).exists():
            cmd += ['--ro-bind', root, root]
    for part in ('src', 'assets', '.agents/skills'):
        cmd += ['--ro-bind', str(Path(aha).resolve() / part), '/aha/' + part]
    cmd += ['--ro-bind', str(Path(blender).parent), '/blender',
            '--bind', str(candidate), '/work']
    for name in ('input.blend', 'candidate.blend', 'build.py', Path(request).name):
        source = candidate / name
        if source.exists():
            cmd += ['--ro-bind', str(source), '/work/' + name]
    cmd += ['--ro-bind', str(Path(script).resolve()), '/runner.py',
            '--chdir', '/work', '/blender/' + Path(blender).name,
            '-b', '--factory-startup', '--disable-autoexec', '--threads', '2',
            '--python-exit-code', '1', '--python', '/runner.py', '--', '/work/' + Path(request).name]
    return cmd


def execute(c, folder, script, request):
    cmd = command(c.blender, c.aha_repo, folder, script, request)
    logfile = Path(folder) / ('blender-' + Path(request).stem + '.log')
    with logfile.open('w') as log:
        result = run_process(cmd, timeout=c.timeout_s, stdout=log, stderr=log,
                             env={'PATH': os.environ.get('PATH', '/usr/bin:/bin')})
    if result.returncode:
        tail = logfile.read_text(errors='replace')[-6000:]
        raise RuntimeError(f'Isolated Blender failed ({result.returncode}); see {logfile}\n{tail}')
