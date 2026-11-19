"""Inspect a room's native views and navigable positions before capture."""
import argparse,json
from pathlib import Path
from PIL import Image,ImageDraw
from ai2thor.controller import Controller
from ai2thor.platform import CloudRendering
p=argparse.ArgumentParser();p.add_argument('scene');a=p.parse_args()
root=Path(__file__).resolve().parents[1]/'datasets/ai2thor'
out=root/'inspection'/a.scene;out.mkdir(parents=True,exist_ok=False)
class LocalController(Controller):
 @property
 def base_dir(self):return str(out/'runtime_cache')
build=json.loads((root/'download_manifest.json').read_text())
c=LocalController(local_executable_path=build['executable'],platform=CloudRendering,scene=a.scene,width=960,height=640,quality='Ultra',fieldOfView=70,snapToGrid=False)
try:
 m=c.last_event.metadata
 (out/'initial_metadata.json').write_text(json.dumps(m,indent=2))
 e=c.step(action='GetReachablePositions',gridSize=.25)
 assert e.metadata['lastActionSuccess'],e.metadata['errorMessage']
 (out/'reachable.json').write_text(json.dumps(e.metadata['actionReturn'],indent=2))
 sheet=Image.new('RGB',(1920,696),'white');draw=ImageDraw.Draw(sheet)
 for i,yaw in enumerate(range(0,360,45)):
  e=c.step(action='TeleportFull',position=m['agent']['position'],rotation={'x':0,'y':yaw,'z':0},horizon=12,standing=True)
  assert e.metadata['lastActionSuccess'],e.metadata['errorMessage']
  e=c.step(action='Pass');im=Image.fromarray(e.frame);im.save(out/f'yaw_{yaw:03d}.png')
  x=(i%4)*480;y=(i//4)*348;sheet.paste(im.resize((480,320)),(x,y+28));draw.text((x+4,y+4),str(yaw),fill='black')
 sheet.save(out/'views.jpg',quality=95)
 print(a.scene,'reachable',len(json.loads((out/'reachable.json').read_text())),'objects',len(m['objects']),flush=True)
finally:c.stop()
