"""Rebuild the paper diagram as editable SVG/HTML and a 2x-resolution PNG.
Uses only Pillow; shapes and labels are emitted from the same source to both formats.
"""
from pathlib import Path
from html import escape
from PIL import Image, ImageDraw, ImageFont
import math
OUT = Path(__file__).resolve().parent
W,H,S=1600,780,2
im=Image.new('RGB',(W*S,H*S),'white'); d=ImageDraw.Draw(im)
svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', '<rect width="100%" height="100%" fill="white"/>']
INK='#183044'; MUTED='#4f6573'; BLUE='#28649b'; TEAL='#137c75'; ORANGE='#a65c24'; LINE='#a7b7c2'
def box(x,y,w,h,fill='white',stroke=LINE,r=12):
 d.rounded_rectangle((x*S,y*S,(x+w)*S,(y+h)*S),r*S,fill=fill,outline=stroke,width=2*S)
 svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
def txt(x,y,t,size=29,color=INK,bold=False,center=False):
 size=max(28,size)
 font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans'+('-Bold' if bold else '')+'.ttf',size*S)
 if center: x-=d.textlength(t,font=font)/(2*S)
 d.text((x*S,y*S),t,font=font,fill=color)
 svg.append(f'<text x="{x}" y="{y+size*.94}" font-family="DejaVu Sans, sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{escape(t)}</text>')
def arrow(points,color=MUTED,dashed=False):
 for (x,y),(xx,yy) in zip(points,points[1:]):
  if dashed:
   n=max(1,int(math.hypot(xx-x,yy-y)/12))
   for k in range(0,n,2):
    a=k/n;b=min(k+1,n)/n
    d.line(((x+(xx-x)*a)*S,(y+(yy-y)*a)*S,(x+(xx-x)*b)*S,(y+(yy-y)*b)*S),fill=color,width=3*S)
  else:d.line((x*S,y*S,xx*S,yy*S),fill=color,width=3*S)
 x,y=points[-1];px,py=points[-2];ang=math.atan2(y-py,x-px)
 tip=[(x,y),(x-13*math.cos(ang-.45),y-13*math.sin(ang-.45)),(x-13*math.cos(ang+.45),y-13*math.sin(ang+.45))]
 d.polygon([(a*S,b*S) for a,b in tip],fill=color)
 pts=' '.join(f'{a},{b}' for a,b in points)
 dash=' stroke-dasharray="7 5"' if dashed else ''
 svg.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="3"{dash}/>')
 svg.append('<polygon points="'+' '.join(f'{a},{b}' for a,b in tip)+f'" fill="{color}"/>')
# Two alternative policies use exactly the same substrate.
box(16,14,762,93,'#eff5fc','#abc4db');box(800,14,784,93,'#edf7f5','#a5cdc8')
txt(397,25,'AHA-auto',33,BLUE,True,True);txt(397,66,'Code advances waves and bounded retries',27,center=True)
txt(1192,25,'AHA-agent-driven',33,TEAL,True,True);txt(1192,66,'Supervisor chooses each wave and repair',27,center=True)
arrow([(397,107),(397,137),(800,137),(800,166)])
arrow([(1192,107),(1192,137),(800,137)])
txt(800,169,'SHARED DEPENDENCY-SAFE EXECUTION',29,INK,True,True)
# Three panels.
box(16,222,470,369,'#f7f9fc','#b8c5d1')
box(520,222,466,369,'#f0f8f7','#9ac8c2')
box(1020,222,564,369,'#f8f7f3','#c9c1ae')
txt(40,238,'1  Select a safe wave',31,BLUE,True)
txt(40,283,'Dependencies committed',27)
txt(40,320,'No read/write conflicts',27)
box(40,373,192,59,'white',BLUE);box(252,373,210,59,'white',BLUE)
txt(136,385,'Desk',28,BLUE,True,True);txt(357,385,'Chair',28,BLUE,True,True)
arrow([(136,432),(136,467)],ORANGE,dashed=True)
box(40,468,422,57,'#fff4e9','#d9b28c')
txt(251,480,'Lamp waits for desk commit',26,ORANGE,False,True)
txt(40,548,'Ready tasks; bounded capacity',25,MUTED)
arrow([(486,402),(520,402)],BLUE)
txt(544,238,'2  Build in parallel',31,TEAL,True)
txt(544,283,'Same parent revision r',27)
box(544,344,418,76,'white',TEAL);box(544,442,418,76,'white',TEAL)
txt(753,354,'Desk: isolated build',24,TEAL,True,True)
txt(753,386,'Candidate A; scoped IDs',24,MUTED,center=True)
txt(753,452,'Chair: isolated build',24,TEAL,True,True)
txt(753,484,'Candidate B; scoped IDs',24,MUTED,center=True)
txt(544,548,'No shared-scene writes',24,MUTED)
arrow([(986,402),(1020,402)],TEAL)
txt(1044,238,'3  Verify and commit',31,INK,True)
txt(1044,283,'One writer; each candidate in turn',27)
box(1044,337,516,54,'white',LINE);txt(1302,348,'Scoped import into current scene',26,center=True)
arrow([(1302,391),(1302,414)])
box(1044,414,516,65,'white',LINE);txt(1302,432,'Fresh checks + bound review',28,center=True)

arrow([(1302,479),(1302,502)])
box(1044,502,516,55,'#e8f4ee','#85b79d');txt(1302,513,'Pass → commit new revision',26,TEAL,True,True)
# Bottom constraint and review outcome bands.
box(16,616,970,74,'#f5f7fa','#b8c5d1')
txt(501,625,'Shared limits: ≤4 builds · ≤4 model calls · 1 GPU job',27,INK,True,True)
txt(501,658,'Lowered by CPU / memory limits',22,MUTED,center=True)
box(1020,616,564,74,'#fff4e9','#d9b28c')
txt(1302,626,'Fail → retain for repair',25,ORANGE,True,True)
txt(1302,657,'No shared-scene commit',23,ORANGE,center=True)
arrow([(1065,479),(1003,479),(1003,649),(1020,649)],ORANGE,dashed=True)
arrow([(1302,557),(1595,557),(1595,727),(1546,727)],TEAL)
box(16,707,1530,57,'white','#b8c5d1')
txt(781,719,'Commits unlock the next wave  •  The native AHA gate checks the final layout',27,INK,False,True)
svg.append('</svg>')
(OUT/'parallelism.svg').write_text('\n'.join(svg))
(OUT/'parallelism.html').write_text('<!doctype html><html><meta charset="utf-8"><title>Agentic scene reconstruction: parallel execution</title><style>body{margin:0;background:white}svg{display:block;width:100%;height:auto;max-width:1600px;margin:auto}</style>'+ '\n'.join(svg)+'</html>')
im.save(OUT/'parallelism.png',dpi=(600,600))
