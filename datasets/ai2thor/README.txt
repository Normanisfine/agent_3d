Original AI2-THOR dataset / simulator assets

Selected scene: FloorPlan209 (living room).
AI2-THOR 5.0.0, build f0825767cd50d69f666c7f282e54abfe58f1e917.
The official CloudRendering archive contains bundled scenes, including FloorPlan209.
It is a Unity simulator asset package, not a standalone GLB or a reconstruction run.
The original downloaded ZIP is retained; releases/ contains the extracted build.
SHA256 matches the previously recorded official downloader checksum; ZIP CRC checked.
scene_config.json selects FloorPlan209 and records the local executable path.
No reconstruction outputs were copied. No simulator launch was performed.

To load using the existing environment:
/home/mj/dl_project/envs/ai2thor/bin/python

from ai2thor.controller import Controller
controller = Controller(scene="FloorPlan209", local_executable_path="/home/mj/dl_project/agen3d/datasets/ai2thor/releases/thor-CloudRendering-f0825767cd50d69f666c7f282e54abfe58f1e917/thor-CloudRendering-f0825767cd50d69f666c7f282e54abfe58f1e917", width=960, height=640)
# Access controller.last_event.frame / metadata, then controller.stop().

Source: https://github.com/allenai/ai2thor
Scene documentation: https://ai2thor.allenai.org/ithor/documentation/scenes/
