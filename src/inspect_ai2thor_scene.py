"""List exact scene-name matches in the pinned local build."""
import argparse
import json
import re
from pathlib import Path
from ai2thor.controller import Controller
from ai2thor.platform import CloudRendering

p=argparse.ArgumentParser()
p.add_argument('scene')
a=p.parse_args()
root=Path(__file__).resolve().parents[1]/'datasets/ai2thor'
build=json.loads((root/'download_manifest.json').read_text())
class LocalController(Controller):
    @property
    def base_dir(self):
        return str(root/'inspection_runtime_cache')
c=LocalController(local_executable_path=build['executable'], platform=CloudRendering,
                  scene='FloorPlan209', width=320, height=240, server_start_timeout=120)
try:
    e=c.step(action='GetScenesInBuild')
    if not e.metadata['lastActionSuccess']: raise RuntimeError(e.metadata['errorMessage'])
    scenes=e.metadata['actionReturn']
    number = re.search(r'\d+', a.scene)
    matches=[s for s in scenes if a.scene.lower() in s.lower()
             or (number and re.search(r'\d+', s) and re.search(r'\d+', s).group() == number.group())]
    report={'requested':a.scene,'exact_match':a.scene in scenes,'related_matches':matches,'scenes':scenes}
    (root/'available_scenes.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='scenes'},indent=2))
finally:
    c.stop()
