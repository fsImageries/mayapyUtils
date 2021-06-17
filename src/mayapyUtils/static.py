import os


# ------------------------- Maya information -------------------------- #
# --------------------------------------------------------------------- #

project_folders = [
    "assets", "autosave",
    "cache/nCache/fluid",
    "cache/particles",
    "clips", "data", "images", "movies",
    "renderData/depth",
    "renderData/fur",
    "renderData/fur/furAttrMap",
    "renderData/fur/furEqualMap",
    "renderData/fur/furFiles",
    "renderData/fur/furImages",
    "renderData/fur/furShadowMap",
    "renderData/iprImages",
    "renderData/shaders",
    "sceneAssembly"
    "scenes/edits",
    "scripts", "sound",
    "sourceimages/3dPaintTextures",
    "Time Editor/Clip Exports"
]


workspace_definition = """
//Maya 2020 Project Definition

workspace -fr "fluidCache" "cache/nCache/fluid";
workspace -fr "images" "images";
workspace -fr "offlineEdit" "scenes/edits";
workspace -fr "furShadowMap" "renderData/fur/furShadowMap";
workspace -fr "iprImages" "renderData/iprImages";
workspace -fr "FBX" "data";
workspace -fr "SVG" "data";
workspace -fr "renderData" "renderData";
workspace -fr "scripts" "scripts";
workspace -fr "fileCache" "cache/nCache";
workspace -fr "eps" "data";
workspace -fr "DAE_FBX" "data";
workspace -fr "shaders" "renderData/shaders";
workspace -fr "3dPaintTextures" "sourceimages/3dPaintTextures";
workspace -fr "translatorData" "data";
workspace -fr "mel" "scripts";
workspace -fr "furFiles" "renderData/fur/furFiles";
workspace -fr "OBJ" "data";
workspace -fr "particles" "cache/particles";
workspace -fr "scene" "scenes";
workspace -fr "FBX export" "data";
workspace -fr "furEqualMap" "renderData/fur/furEqualMap";
workspace -fr "sourceImages" "sourceimages";
workspace -fr "furImages" "renderData/fur/furImages";
workspace -fr "clips" "clips";
workspace -fr "DAE_FBX export" "data";
workspace -fr "depth" "renderData/depth";
workspace -fr "sceneAssembly" "sceneAssembly";
workspace -fr "teClipExports" "Time Editor/Clip Exports";
workspace -fr "movie" "movies";
workspace -fr "audio" "sound";
workspace -fr "autoSave" "autosave";
workspace -fr "mayaAscii" "scenes";
workspace -fr "move" "data";
workspace -fr "sound" "sound";
workspace -fr "diskCache" "data";
workspace -fr "illustrator" "data";
workspace -fr "mayaBinary" "scenes";
workspace -fr "templates" "assets";
workspace -fr "OBJexport" "data";
workspace -fr "furAttrMap" "renderData/fur/furAttrMap";
workspace -fr "timeEditor" "Time Editor";
"""


# ------------------- aimocap mahelper information -------------------- #
# --------------------------------------------------------------------- #


HOST = "localhost"
PORT = 6550
HEADER_SIZE = 10


CocoPairs = [
    (1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6,
                                             7), (1, 8), (8, 9), (9, 10), (1, 11),
    (11, 12), (12, 13), (1, 0), (0, 14), (14,
                                          16), (0, 15), (15, 17), (2, 16), (5, 17)
]

VideoPosePairs = [[0, 4], [4, 5], [5, 6],
                  [0, 1], [1, 2], [2, 3],
                  [0, 7], [7, 8], [8, 9], [9, 10],
                  [8, 11], [11, 12], [12, 13],
                  [8, 14], [14, 15], [15, 16]]

VideoPoseNames = {0: "Hip", 1: "rThigh", 2: "rShin", 3: "rFoot",
                  4: "lThigh", 5: "lShin", 6: "lFoot",
                  7: "upperSpine", 8: "lowerSpine", 9: "Neck", 10: "Head",
                  11: "lShoulder", 12: "lElbow", 13: "lHand",
                  14: "rShoulder", 15: "rElbow", 16: "rHand"}

VideoPoseNamesRev = {v: k for k, v in VideoPoseNames.items()}

aimocap_commands = ["""
    import json
    from mayapyUtils import mahelper

    json_file = mahelper.get_filePath(ff="*.json", cap="Open .json file.")
    if json_file:
        with open(json_file[0]) as json_data:
            data = json.load(json_data)

        mahelper.VideoPose3DMayaServer(parent=mahelper.getMayaWin(),mult=1,static=True).process_data(data)
    """, """
    from mayapyUtils import mahelper

    try:
        server.deleteLater()
    except:
        pass
        
    cmds.evalDeferred("server = mahelper.VideoPose3DMayaServer(parent=mahelper.getMayaWin(),mult=1)")
    """]

aimocap_shelfname = "Custom"
aimocap_shelftool = {
    "label": ["aiSkel", "aiServer"],
    "command": aimocap_commands,
    "annotation": ["Import VideoPose3D json skelet.",
                   "Activate server-side of the maya skeleton creation, listens for incoming data and disconnects after processing."],
    "image1": "pythonFamily.png",
    "sourceType": "python",
    "imageOverlayLabel": ["aiSkel", "aiServer"]
}


# --------------------- aimocap.py information ------------------------ #
# --------------------------------------------------------------------- #


VideoPoseChains = [[0, 1, 2, 3], [0, 4, 5, 6], [7, 8, 9, 10], [11, 12, 13], [14, 15, 16]]

Skips = [0, 7, 11, 14]


# ---------------------- basicMayaIO Information ---------------------- #
# --------------------------------------------------------------------- #

