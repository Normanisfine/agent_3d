"""Conservative host calibration and dependency/conflict-aware build waves."""
import math
import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..store import save
from .contracts import Plan


def machine_snapshot():
    cpus = len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else (os.cpu_count() or 1)
    mem = {}
    try:
        mem = {line.split(':')[0]: int(line.split()[1]) * 1024
               for line in Path('/proc/meminfo').read_text().splitlines()}
    except (OSError, ValueError):
        pass
    available = mem.get('MemAvailable', 2 * 1024**3)
    # Respect cgroup v2 container limits as well as the host's free memory/CPU.
    try:
        group = next(line.split(':', 2)[2] for line in Path('/proc/self/cgroup').read_text().splitlines()
                     if line.startswith('0::'))
        folder = Path('/sys/fs/cgroup') / group.lstrip('/')
        while True:
            try:
                quota, period = (folder / 'cpu.max').read_text().split()
                if quota != 'max':
                    cpus = min(cpus, max(1, math.floor(int(quota) / int(period))))
            except (OSError, ValueError):
                pass
            try:
                limit = (folder / 'memory.max').read_text().strip()
                if limit != 'max':
                    available = min(available, max(0, int(limit) - int((folder / 'memory.current').read_text())))
            except (OSError, ValueError):
                pass
            if folder == Path('/sys/fs/cgroup') or Path('/sys/fs/cgroup') not in folder.parents:
                break
            folder = folder.parent
    except (OSError, StopIteration):
        pass
    load = os.getloadavg()[0] if hasattr(os, 'getloadavg') else 0.
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.free', '--format=csv,noheader'],
                                capture_output=True, text=True, timeout=5)
        gpu = result.stdout.strip() if result.returncode == 0 else 'unavailable'
    except (OSError, subprocess.TimeoutExpired):
        gpu = 'unavailable'
    return {'effective_cpus': cpus, 'load_1m': load, 'available_memory_gib': available / 1024**3,
            'gpu': gpu}


def limits(snapshot, policy):
    cpu_slots = max(1, int(max(1, snapshot['effective_cpus'] - snapshot['load_1m']) * .75) // 2)
    mem_slots = max(1, int(snapshot['available_memory_gib'] * .7 / policy.memory_per_build_gib))
    return {'builds': min(policy.max_builds, cpu_slots, mem_slots) if policy.enabled else 1,
            'model_calls': min(policy.max_model_calls, max(1, int(snapshot['available_memory_gib'] / .5))) if policy.enabled else 1,
            'gpu_jobs': 1}


def calibrate(config, output, *, benchmark=None):
    """No paid calls. Benchmark isolated Blender startup/mesh/save, not model throughput."""
    from .isolation import execute
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    snapshot = machine_snapshot()
    chosen = limits(snapshot, config.parallelism)
    samples = []
    error = None
    do_benchmark = config.parallelism.benchmark if benchmark is None else benchmark
    if do_benchmark and config.parallelism.enabled:
        script = output / 'probe.py'
        script.write_text('''import bpy, bmesh
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for i in range(12):
    mesh = bpy.data.meshes.new(str(i))
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=5, radius=1)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(str(i), mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location.x = i * 3
bpy.ops.wm.save_as_mainfile(filepath='/work/probe.blend')
bpy.ops.wm.open_mainfile(filepath='/work/probe.blend', load_ui=False)
assert len(bpy.context.scene.objects) == 12
''')
        try:
            for count in sorted({1, min(2, chosen['builds']), chosen['builds']}):
                folders = [output / f'probe-{count}-{i}' for i in range(count)]
                for folder in folders:
                    folder.mkdir(exist_ok=False)
                    save(folder / 'request.json', {})
                start = time.monotonic()
                with ThreadPoolExecutor(max_workers=count) as pool:
                    futures = [pool.submit(execute, config, folder, script, folder / 'request.json') for folder in folders]
                    for future in futures:
                        future.result()
                elapsed = time.monotonic() - start
                samples.append({'workers': count, 'seconds': elapsed, 'jobs_per_second': count / elapsed})
                for folder in folders:
                    (folder / 'probe.blend').unlink(missing_ok=True)
            best = max(s['jobs_per_second'] for s in samples)
            chosen['builds'] = min(s['workers'] for s in samples if s['jobs_per_second'] >= .9 * best)
        except Exception as exc:
            error = str(exc)
            chosen['builds'] = 1
    result = {'machine': snapshot, 'selected': chosen, 'benchmark': samples, 'benchmark_error': error,
              'basis': 'Smallest tested concurrency within 90% of best synthetic throughput; hardware caps apply.' if samples else 'Conservative hardware/load estimate.',
              'limitations': 'Not a proven optimum for this scene or provider. Model/API rate limits are not benchmarked. GPU jobs remain serial. Limits can be lowered by config.'}
    save(output / 'capacity.json', result)
    return result


def dependency_plan(plan):
    """Honor semantic dependencies; add ordered read/write conflicts and global barriers."""
    tasks = []
    added = []
    for task in plan.tasks:
        deps = set(task.depends_on)
        for earlier in tasks:
            write, read = set(task.object_ids), set(task.reads_object_ids)
            prior_write, prior_read = set(earlier.object_ids), set(earlier.reads_object_ids)
            reason = ('exclusive scene task' if not task.parallel_safe or not earlier.parallel_safe
                      else 'object read/write conflict' if write & (prior_write | prior_read) or read & prior_write else None)
            if reason and earlier.task_id not in deps:
                deps.add(earlier.task_id)
                added.append({'from': earlier.task_id, 'to': task.task_id, 'reason': reason})
        tasks.append(task.model_copy(update={'depends_on': [t.task_id for t in tasks if t.task_id in deps]}))
    return Plan(summary=plan.summary, tasks=tasks), added


def ready_tasks(plan, results, count):
    ready = []
    for task in plan.tasks:
        if task.task_id in results:
            continue
        if all(dep in results and results[dep]['status'] == 'candidate_committed' for dep in task.depends_on):
            ready.append(task)
            if not task.parallel_safe or len(ready) == count:
                break
    return ready


class HostMeter:
    """Allocate each overlapping host interval once, equally among active operations."""
    def __init__(self):
        self.lock = threading.Lock()
        self.active = {}
        self.last = time.monotonic()

    def tick(self, now):
        if self.active:
            share = (now - self.last) / len(self.active)
            for key in self.active:
                self.active[key] += share
        self.last = now

    def start(self, key):
        with self.lock:
            self.tick(time.monotonic())
            self.active[key] = 0.

    def finish(self, key):
        with self.lock:
            self.tick(time.monotonic())
            return self.active.pop(key)
