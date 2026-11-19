"""Create an inward-looking capture route using FloorPlan206's reachable grid."""
import json
from collections import deque
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'datasets/ai2thor'
scout=root/'inspection/FloorPlan206'
positions=json.loads((scout/'reachable.json').read_text())
nodes={(round(p['x']*4),round(p['z']*4)) for p in positions}
anchors=[(1.75,.75),(1.5,.25),(0,.25),(-1,.25),(-1,-.5),(-1,-1.25),
         (-.75,-1.75),(.5,-1.75),(1.25,-1.75),(1.5,-.5),(1.75,.75)]
anchors=[(round(x*4),round(z*4)) for x,z in anchors]
assert all(p in nodes for p in anchors)
route=[anchors[0]]
for target in anchors[1:]:
 q=deque([route[-1]]);parents={route[-1]:None}
 while q and target not in parents:
  x,z=q.popleft()
  for p in ((x+1,z),(x-1,z),(x,z+1),(x,z-1)):
   if p in nodes and p not in parents:parents[p]=(x,z);q.append(p)
 assert target in parents
 path=[];p=target
 while parents[p] is not None:path.append(p);p=parents[p]
 route.extend(reversed(path))
result={'scene':'FloorPlan206','waypoints_xz':[[x/4,z/4] for x,z in route],
        'look_at_xz':[0.,-.6],'horizon_degrees':12,
        'source':'Grid-connected route through native GetReachablePositions; original furnishings preserved'}
(sc_out:=scout/'trajectory.json').write_text(json.dumps(result,indent=2)+'\n')
print(sc_out,'segments',len(route)-1,'length_m',(len(route)-1)*.25)
