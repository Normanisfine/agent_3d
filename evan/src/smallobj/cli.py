"""agent 用的命令行工具（scripts/agent_tools/ 下的包装脚本调这里）。只读 perception/、gen/，不碰 scenes/。

  gen3d-request --scene S --items a,b [--backend B] [--inventory F]   后台生成，立即打印 job_id
  gen3d-status JOB --scene S                                          打印任务文件
  place-mesh --scene S --item I --candidate K [--dof 7] [--support-z Z]  打印 PlacementResult
每次 agent 运行的生成次数单独计数（环境变量 SMALLOBJ_BUDGET，run_agent.sh 设成 budget_<arm>_s<seed>），上限 30。
"""
import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from smallobj import gen3d, place

PROJ = Path(__file__).resolve().parents[2]


def _job_path(root, scene, job_id):
    return Path(root) / "gen" / scene / "jobs" / f"{job_id}.json"


def _run_job(root, scene, job_id):
    p = _job_path(root, scene, job_id)
    job = json.loads(p.read_text())
    try:
        res = gen3d.request(scene, job["items"], backend=job["backend"], n_candidates=job["n_candidates"],
                            inventory=job["inventory"], root=Path(root), budget_name=job["budget_name"])
        job.update(status="done", results=res)
    except Exception as e:  # noqa: BLE001 — 任务文件里记下原因，agent 读得到
        job.update(status="error", error=str(e)[:500])
    job["finished"] = time.time()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(job, indent=1) + "\n")
    tmp.replace(p)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="smallobj.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("gen3d-request")
    r.add_argument("--scene", required=True)
    r.add_argument("--items", required=True)
    r.add_argument("--backend", default="hy3d_shape")
    r.add_argument("--inventory", default="inventory.json")
    r.add_argument("--n-candidates", type=int, default=2)
    r.add_argument("--root", default=str(PROJ))
    r.add_argument("--sync", action="store_true", help="同步跑完（测试用）")
    s = sub.add_parser("gen3d-status")
    s.add_argument("job_id")
    s.add_argument("--scene", required=True)
    s.add_argument("--root", default=str(PROJ))
    w = sub.add_parser("_worker")
    w.add_argument("job_id")
    w.add_argument("--scene", required=True)
    w.add_argument("--root", default=str(PROJ))
    m = sub.add_parser("place-mesh")
    m.add_argument("--scene", required=True)
    m.add_argument("--item", required=True)
    m.add_argument("--candidate", type=int, required=True)
    m.add_argument("--dof", type=int, default=7)
    m.add_argument("--support-z", type=float, default=None)
    m.add_argument("--inventory", default="inventory.json")
    m.add_argument("--root", default=str(PROJ))
    a = ap.parse_args(argv)
    if a.cmd == "gen3d-request":
        job_id = time.strftime("%H%M%S") + "-" + uuid.uuid4().hex[:6]
        p = _job_path(a.root, a.scene, job_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"job_id": job_id, "status": "running", "items": a.items.split(","), "backend": a.backend,
                                 "inventory": a.inventory, "n_candidates": a.n_candidates, "started": time.time(),
                                 "budget_name": os.environ.get("SMALLOBJ_BUDGET", "budget")}, indent=1) + "\n")
        if a.sync:
            _run_job(a.root, a.scene, job_id)
        else:
            subprocess.Popen([sys.executable, "-m", "smallobj.cli", "_worker", job_id, "--scene", a.scene, "--root", a.root],
                             stdout=subprocess.DEVNULL, stderr=open(p.with_suffix(".log"), "w"), start_new_session=True)
        print(job_id)
    elif a.cmd == "_worker":
        _run_job(a.root, a.scene, a.job_id)
    elif a.cmd == "gen3d-status":
        print(_job_path(a.root, a.scene, a.job_id).read_text())
    elif a.cmd == "place-mesh":
        res = place.place_mesh(a.scene, a.item, a.candidate, dof=a.dof, support_z=a.support_z,
                               inventory=a.inventory, root=Path(a.root))
        print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
