"""Render measured process intervals; bars are lifetimes, not exclusive GPU time."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('profile',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():p.error('Output must be new')
    data=json.loads(a.profile.read_text())
    labels={'source_capture':'Source capture','reference_preparation':'Reference preparation',
            'object_segmentation':'Object segmentation','authored_build_and_stills':'Build + still renders',
            'layout_evidence':'Layout evidence','preview_render':'Preview render',
            'external_review':'External review','saved_scene_validation':'Saved-scene validation',
            'compaction':'Context compaction'}
    fig,ax=plt.subplots(figsize=(12,6))
    for i,(key,label) in enumerate(labels.items()):
        rows=data['compactions'] if key=='compaction' else [r for r in data['commands'] if r['category']==key]
        for row in rows:
            failed=row.get('exit_code',0) not in (0,None)
            ax.broken_barh([(row['start_offset_s']/60,row['wall_seconds']/60)],(i-.32,.64),
                          facecolors='#bf5b40' if failed else '#376b87',edgecolors='none')
    ax.set_yticks(range(len(labels)),labels.values());ax.invert_yaxis()
    ax.set_xlim(0,data['observed_wall_seconds']/60)
    ax.set_xlabel('Elapsed time from original task start (minutes)');ax.set_ylabel('Recorded process / event')
    ax.set_title('Original AHA FloorPlan209: measured process lifetimes',loc='left',fontweight='bold')
    ax.grid(axis='x',alpha=.18);ax.set_axisbelow(True)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color='#376b87',label='Exit 0 / compaction event'),
                       Patch(color='#bf5b40',label='Nonzero exit / terminated')],loc='upper right',frameon=False)
    fig.text(.02,.025,'Source: original session, 2026-10-22 23:36:15–2026-10-23 00:18:22 UTC.\n'
             'Intervals overlap; blank space includes controller activity and unmeasured overhead. Not a GPU utilization chart.',fontsize=9)
    fig.tight_layout(rect=[0,.08,1,1]);fig.savefig(a.output,dpi=160);plt.close(fig)


if __name__=='__main__':main()
