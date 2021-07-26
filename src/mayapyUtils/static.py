# -------------------- Server/Client Information ---------------------- #
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
