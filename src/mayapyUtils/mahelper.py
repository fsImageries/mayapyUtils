import maya.api.OpenMayaAnim as api2a
import maya.api.OpenMaya as api2
import maya.OpenMayaUI as apiUI
import maya.cmds as cmds


from shiboken2 import wrapInstance, getCppPointer
from PySide2 import QtWidgets, QtCore
from contextlib import contextmanager
from pyside2uic import compileUi
from maya import mel


import pyhelper
import static
import sys
import os


# --------------------------- Shelf Tools ----------------------------- #
# --------------------------------------------------------------------- #


def create_shelfs(nth=2, tool=static.aimocap_shelftool, name=static.aimocap_shelfname):
    for i in range(nth):
        shelf_tool = {}
        for k, v in tool.items():
            shelf_tool[k] = v if isinstance(v, str) else v[i]
        try:
            _set_shelfBTN(shelf_tool, name)
        except Exception as err:
            print("[ERROR] An error occured: {0}".format(err))


def _set_shelfBTN(shelf_tool, shelf_name):
    # get top shelf
    gShelfTopLevel = mel.eval("$tmpVar=$gShelfTopLevel")
    # get top shelf names
    shelves = cmds.tabLayout(gShelfTopLevel, query=1, ca=1)
    # create shelf
    if shelf_name not in shelves:
        cmds.shelfLayout(shelf_name, parent=gShelfTopLevel)
    # delete existing button
    _remove_shelfBTN(shelf_tool, shelf_name)
    # add button
    cmds.shelfButton(style="iconOnly", parent=shelf_name, **shelf_tool)


def _remove_shelfBTN(shelf_tool, shelf_name):
    # get existing members
    names = cmds.shelfLayout(shelf_name, query=True, childArray=True) or []
    labels = [cmds.shelfButton(n, query=True, label=True) for n in names]

    # delete existing button
    if shelf_tool.get("label") in labels:
        index = labels.index(shelf_tool.get("label"))
        cmds.deleteUI(names[index])


# --------------------- Workspace Control Setups ---------------------- #
# --------------------------------------------------------------------- #


class WorkspaceControl(object):

    def __init__(self, name):
        # -construct with a given workspace_control name
        self.name = name
        self.widget = None

    def create(self, label, widget, uiScript=None, plugin=None):
        """
        Create a workspace_control with the given name and label.

        Args:
            label ([String]): Displayed Text label on the workspace_control.
            widget ([QWidget]): The Ui or widget which should be parent to mayas layout.
            uiScript ([String], optional): Python-string which should generate the Ui. 
                                           Defaults to None.
        """
        if not plugin:
            cmds.workspaceControl(self.name, label=label)
        else:
            cmds.workspaceControl(self.name, label=label,
                                  checksPlugins=True, requiredPlugin="shaderHelper.py")

        # -supply the control with a ui-creation script
        if uiScript:
            cmds.workspaceControl(self.name, e=True, uiScript=uiScript)

        self.add_widgetToLayout(widget)
        self.set_visible(True)

    def add_widgetToLayout(self, widget):
        """
        Retrieve the workspace_control and widget as pointers and add them
        to the main maya layout.

        Args:
            widget ([QWidget]): The Ui or widget which should be parent to mayas layout. 
        """
        if widget:
            self.widget = widget

            # maya.app.general.mayaMixin
            # If the input parent happens to be a Native window (such as the main Maya
            # window) then when we are parented to it, we also become a Native window.
            # Being a Native window is okay, but we don't want our ancestors to be
            # switched to Native, such as when we are docked inside a tabWidget.
            self.widget.setAttribute(QtCore.Qt.WA_DontCreateNativeAncestors)

            workspaceControl_ptr = long(apiUI.MQtUtil.findControl(self.name))
            widget_ptr = long(getCppPointer(self.widget)[0])

            apiUI.MQtUtil.addWidgetToMayaLayout(
                widget_ptr, workspaceControl_ptr)

    def restore(self, widget):
        """
        Restore the widget.

        Args:
            widget ([QWidget]): The Ui or Widget which should be restored.
        """
        self.add_widgetToLayout(widget)

    def exists(self):
        """
        Check if the given workspace_control exits.

        Returns:
            [Bool]: True if existing.
        """
        return cmds.workspaceControl(self.name, q=True, exists=True)

    def is_visible(self):
        """
        Check if the given workspace_control is visible.

        Returns:
            [Bool]: True if visible.
        """
        return cmds.workspaceControl(self.name, q=True, visible=True)

    def is_floating(self):
        """
        Check if the given workspace_control is floating.

        Returns:
            [Bool]: True if floating.
        """
        return cmds.workspaceControl(self.name, q=True, floating=True)

    def is_collapsed(self):
        """
        Check if the given workspace_control is collapsed.

        Returns:
            [Bool]: True if collapsed.
        """
        return cmds.workspaceControl(self.name, q=True, collapse=True)

    def set_visible(self, visible):
        """
        Sets the visibility of the workspace_control.

        Args:
            visible ([Bool]): Determines if the workspace_control should be invisible or restored.
        """
        if visible:
            cmds.workspaceControl(self.name, e=True, restore=True)
        else:
            cmds.workspaceControl(self.name, e=True, visible=False)

    def set_label(self, label):
        """
        Sets the label of the workspace_control.

        Args:
            label ([String]): The String which should be displayed on the workspace_control.
        """
        cmds.workspaceControl(self.name, e=True, label=label)

    # ----------------------------------UI Helper Methods---------------------------------- #
    # -only used with QT Ui classes
    # -assumes your Ui comes with some Class level name variables:
    #       - UI_NAME: ObjectName of the Ui.
    #       - WINDOW_TITLE: Title that should be displayed in the Ui window.

    @staticmethod
    def get_workspaceControl_name(uiCls):
        return "{0}_workspaceControl".format(uiCls.UI_NAME)

    @staticmethod
    def create_workspaceControl(UiSelf):
        UiSelf.workspaceControl_instance = WorkspaceControl(
            WorkspaceControl.get_workspaceControl_name(UiSelf))

        if UiSelf.workspaceControl_instance.exists():
            UiSelf.workspaceControl_instance.restore(UiSelf)
        else:
            UiSelf.workspaceControl_instance.create(
                UiSelf.WINDOW_TITLE, UiSelf, UiSelf.get_uiScript(), getattr(UiSelf, "PLUGIN", None))

    @staticmethod
    def show_workspaceControl(UiSelf):
        UiSelf.workspaceControl_instance.set_visible(True)


# --------------------- PySide2 Server/Client  ------------------------ #
# --------------------------------------------------------------------- #


class ServerBase(QtCore.QObject):

    PORT = static.PORT
    HEADER_SIZE = static.HEADER_SIZE

    def __init__(self, parent):
        super(ServerBase, self).__init__(parent)

        self.port = self.__class__.PORT
        self.initialize()

    def initialize(self):
        self.server = QtNetwork.QTcpServer(self)
        self.server.newConnection.connect(self.establish_connection)

        if self.listen():
            print("[LOG] Server listening on post: {0}".format(self.port))
        else:
            print("[ERROR] Server initialization failed.")

    def listen(self):
        if not self.server.isListening():
            return self.server.listen(QtNetwork.QHostAddress.LocalHost, self.port)

        return False

    def establish_connection(self):
        self.socket = self.server.nextPendingConnection()
        if self.socket.state() == QtNetwork.QTcpSocket.ConnectedState:
            self.socket.disconnected.connect(self.on_disconnect)
            self.socket.readyRead.connect(self.read)

            print("[LOG] Connection established.")

    def on_disconnect(self):
        self.socket.disconnected.disconnect()
        self.socket.readyRead.disconnect()

        self.socket.deleteLater()

        print("[LOG] Connection Disconnected.")

    def read(self):
        bytes_remaining = -1
        json_data = ""

        while self.socket.bytesAvailable():
            # -Header
            if bytes_remaining <= 0:
                byte_array = self.socket.read(ServerBase.HEADER_SIZE)
                bytes_remaining, valid = byte_array.toInt()

                if not valid:
                    bytes_remaining = -1
                    self.write_error("Invalid Header")

                    self.socket.readAll()
                    return

            # -Body
            if bytes_remaining > 0:
                byte_array = self.socket.read(bytes_remaining)
                bytes_remaining -= len(byte_array)
                json_data += byte_array.data().decode()

                if bytes_remaining == 0:
                    bytes_remaining = -1

                    data = json.loads(json_data)

                    self.process_data(data)

                    json_data = ""

    def write(self, data):
        json_reply = json.dumps(data)

        if self.socket.state() == QtNetwork.QTcpSocket.ConnectedState:
            header = "{0}".format(len(json_reply.encode())).zfill(
                ServerBase.HEADER_SIZE)

            data = QtCore.QByteArray(
                "{0}{1}".format(header, json_reply).encode())

            self.socket.write(data)

    def write_error(self, err_msg):
        reply = {
            "success": False,
            "msg": err_msg
        }
        self.write(reply)

    def process_data(self, data):
        print(data)
        self.write({"success": True})


class ClientBase(object):

    PORT = static.PORT
    HEADER_SIZE = static.HEADER_SIZE

    def __init__(self, timeout=2):
        self.timeout = timeout
        self.port = self.__class__.PORT

        self.discard_count = 0

    def connect(self, port=-1):
        if port >= 0:
            self.port = port

        try:
            self.client_socket = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((static.HOST, self.port))
        except:
            traceback.print_exc()
            return False

        return True

    def disconnect(self):
        try:
            self.client_socket.close()
        except:
            traceback.print_exc()
            return False

        return True

    def send(self, data, json_cls=None):
        json_data = json.dumps(data, cls=json_cls)

        message = list()
        message.append("{0:10d}".format(len(json_data.encode())))
        message.append(json_data)

        try:
            msg_str = "".join(message)
            self.client_socket.sendall(msg_str.encode())
        except:
            traceback.print_exc()
            return None

    def recv(self):
        total_data = list()
        data = ""
        reply_length = 0
        bytes_remaining = ClientBase.HEADER_SIZE

        start_time = time()
        while time() - start_time < self.timeout:
            try:
                data = self.client_socket.recv(bytes_remaining)
            except Exception as e:
                print("Exception: {}".format(e))
                sleep(0.01)
                continue

            if data:
                total_data.append(data)

                bytes_remaining -= len(data)
                if(bytes_remaining <= 0):
                    for i in range(len(total_data)):
                        total_data[i] = total_data[i].decode()

                    if reply_length == 0:
                        header = "".join(total_data)
                        reply_length = int(header)
                        bytes_remaining = reply_length
                        total_data = list()
                    else:
                        reply_json = "".join(total_data)
                        return json.loads(reply_json)

        raise RuntimeError("[ERROR] Timeout waiting for response.")

    def is_valid_data(self, data):
        if not data:
            print("[ERROR] Invalid Data.")
            return False

        if not data["success"]:
            print("[ERROR] {0} failed: {1}".format(data["cmd"], data["msg"]))
            return False

        return True

    def ping(self):
        data = {"cmd": "ping"}
        reply = self.send(data)

        if self.is_valid_data(reply):
            return True
        return False


# ---------------------- Maya Server/Client  -------------------------- #
# --------------------------------------------------------------------- #


class O_NectMayaServer(ServerBase):
    """
    Get O-Nect at https://github.com/O-Nect/O-Nect.git


    Start the server in maya like this:
    if __name__ == "__main__":
        import mahelper

        try:
            server.deleteLater()
        except:
            pass

        cmds.evalDeferred("server = mahelper.ServerBase(parent=mahelper.getMayaWin())")
    """

    def __init__(self, parent=None, mult=1, static=None):
        if not static:
            super(O_NectMayaServer, self).__init__(parent)

        self.keyables = dict()
        self.group = None
        self.group_check = True
        self.mult = mult
        self.static = static
        self.pairs = static.CocoPairs

    def process_data(self, data):

        frame_id = data['frame_id']
        iter_id = data["iter_id"]

        mult = self.mult

        newTr = [mult*data['x1_coord'], mult*data['y1_coord']]
        newTr2 = [mult*data['x2_coord'], mult*data['y2_coord']]

        p1_id = data['p1_id']
        p2_id = data['p2_id']

        obj1 = self.get_obj(p1_id)
        obj2 = self.get_obj(p2_id)

        _, _, tz = cmds.xform(obj1, q=True, t=True)
        _, _, tz2 = cmds.xform(obj2, q=True, t=True)
        cmds.xform(obj1, t=newTr+[tz], ws=True)
        cmds.xform(obj2, t=newTr2+[tz2], ws=True)

        if frame_id == 1 and self.group_check:

            # self.grouping()
            self.parenting()
            self.keying()

        elif frame_id >= 1:
            # ls = cmds.listRelatives(self.group)
            # try:
            #     if obj1 not in ls:
            #         cmds.parent(obj1, self.group)

            #     if obj2 not in ls:
            #         cmds.parent(obj2, self.group)
            # except:
            #     pass
            self.parenting()
            self.keying(frame_id)

        if not self.static:
            self.write({"success": True})

    def keying(self, frame_id=0):
        for obj in self.keyables.values():
            cmds.setKeyframe(obj, at="translate", t=frame_id+1)

    def grouping(self):
        # self.group = cmds.group(*self.keyables.values(), n="skel")
        # cmds.xform(self.group, cp=1)
        # cmds.xform(self.group, ro=(0,0,180))
        # self.group_check = False

        self.group = cmds.group(self.keyables[1], n="skel")
        cmds.xform(self.group, cp=1)
        cmds.xform(self.group, ro=(0, 0, 180))
        self.group_check = False

    def parenting(self):
        for p1, p2 in self.pairs:
            try:
                top = self.keyables[p1]
                bottom = self.keyables[p2]
            except KeyError:
                continue

            ls = cmds.listRelatives(top)

            if not ls:
                cmds.parent(bottom, top)
            elif bottom not in ls:
                cmds.parent(bottom, top)

    def get_obj(self, p_id):
        if not self.keyables.get(p_id, None):
            obj = self.create_obj()
            obj = cmds.rename(obj, "{0}_pi_{1}".format(obj, p_id))
            self.keyables[p_id] = obj
            return obj
        else:
            return self.keyables[p_id]

    def create_obj(self):
        # return cmds.polySphere()[0]
        jnt = cmds.joint()
        # -important to deselect as else the joints will parent the last selected object and mess up positioning
        cmds.select(cl=True)
        return jnt


class VideoPose3DMayaServer(ServerBase):
    """
    Get VideoPose3D at https://github.com/facebookresearch/VideoPose3D.git 

    Start the server in maya like this:
    if __name__ == "__main__":
        import mahelper

        try:
            server.deleteLater()
        except:
            pass

        cmds.evalDeferred("server = mahelper.VideoPose3DMayaServer(parent=mahelper.getMayaWin(),mult=1)")
    """

    def __init__(self, parent=None, mult=5, static=None, default_obj="joint"):
        if not static:
            super(VideoPose3DMayaServer, self).__init__(parent)

        self.keyables = dict()
        self.group = None
        self.mult = mult
        self.static = static
        self.pairs = static.VideoPosePairs
        self.names = static.VideoPoseNames
        self.default_obj = default_obj
        self.objs = []

    def process_data(self, data):
        self.prep()
        self.objs = [self.create_obj() for _ in range(17)]
        positions, rots = data

        self.set_positions(positions)
        for n, obj in enumerate(self.objs):
            if rots[n] is not None:
                self.set_rotations(obj, rots[n])

        self.parenting()
        self.grouping()
        self.renaming()

        self.success()

    def process_raw(self, data):
        mult = self.mult
        for f, data_1 in enumerate(data):
            for n, data_2 in enumerate(data_1):
                obj = self.get_obj(n)
                self.objs.append(obj)
                mult_data = [i*mult for i in data_2]
                cmds.xform(obj, t=mult_data, ws=True)

            if f == 0 and self.default_obj == "joint":
                self.parenting()
            self.keying(f)

        self.grouping()
        self.renaming()

        self.success()

    def set_rotations(self, obj, rots_split):
        rots_len = len(rots_split[0])
        set_attribute_keyframes(rots_split, rots_len, obj)

    def set_positions(self, positions):
        for i in range(17):
            cmds.xform(self.objs[i], t=positions[i], ws=True)

    def keying(self, frame_id=0):
        for obj in self.keyables.values():
            cmds.setKeyframe(obj, at="translate", t=frame_id+1)

    def grouping(self):
        if self.default_obj == "joint":
            # -objs[0] bcuz joints
            self.group = cmds.group(self.objs[0], n="skel")
        else:
            self.group = cmds.group(*self.objs, n="skel")

        cmds.xform(self.group, cp=1)
        cmds.xform(self.group, ro=(0, 0, 180))

    def parenting(self):
        for p1, p2 in self.pairs:
            top = self.objs[p1]
            bottom = self.objs[p2]

            ls = cmds.listRelatives(top)

            if not ls:
                cmds.parent(bottom, top)
            elif bottom not in ls:
                cmds.parent(bottom, top)

    def renaming(self):
        for k, v in self.names.items():
            obj = self.objs[k]
            ret = cmds.rename(obj, v)
            self.objs[k] = ret

    def get_obj(self, p_id):
        if not self.keyables.get(p_id, None):
            obj = self.create_obj()
            obj = cmds.rename(obj, "{0}_pi_{1}".format(obj, p_id))
            self.keyables[p_id] = obj
            return obj
        return self.keyables[p_id]

    def create_obj(self):
        obj = getattr(cmds, self.default_obj)()

        if not isinstance(obj, basestring if sys.version[0] != 2 else str):
            obj = obj[0]

        # -important to deselect as else the joints will parent the last selected object and mess up positioning
        cmds.select(cl=True)
        return obj

    def prep(self):
        cmds.select(cl=True)
        cmds.currentTime(1)

    def success(self):
        if not self.static:
            self.write({"success": True})

        print(
            "[LOG] Successfully finished processing.\nCreated {0}.".format(self.group))


# --------------------- Private Helper Functions ---------------------- #
# --------------------------------------------------------------------- #


def _get_shaderValues(shader):
    """
    Querry every attribute of a given shader and get the values of that attribute.
    If attributes are compound or have child attributes it will try to get the 
    values of them or skip it.

    Args:
        shader ([String]): Name of the shader.

    Returns:
        [List]: List with all attribute values of the shader.
    """
    attrs = cmds.listAttr(shader)
    # -remove message cuz it's a unique attribute
    attrs.remove("message")

    attrsVals = list()

    for attr in attrs:
        path = attr.split(".")
        if len(path) > 1:
            parent = None
            for i in range(0, len(path)-1):
                size = cmds.getAttr("{0}.{1}".format(
                    shader, path[i]), size=True)

                if parent:
                    parent = "{0}.{1}[{2}]".format(parent, path[i], size)
                else:
                    parent = "{0}[{1}]".format(path[i], size)

            attr = "{0}.{1}".format(parent, path[-1])

        if "compound" in cmds.getAttr("{0}.{1}".format(shader, attr), type=True).lower():
            continue

        val = cmds.getAttr("{0}.{1}".format(shader, attr))
        attrsVals.append(val)
    return attrsVals


# ---------------------- Maya Helper Functions ------------------------ #
# --------------------------------------------------------------------- #


def getMayaWin():
    """
    Return the QMainWindow for the main Maya Window as QWidget.

    Raises:
        RuntimeError: When no maya window can be found.

    Returns:
        [QWidget]: Maya window as QWidget-object.
    """
    winptr = apiUI.MQtUtil.mainWindow()
    if winptr is None:
        raise RuntimeError("No Maya Window found.")

    window = wrapInstance(long(winptr), QtWidgets.QWidget)
    return window


def get_basename(fullpath):
    try:
        return fullpath.rsplit("|", 1)[1]
    except IndexError:
        print("[LOG] Not a valid path, return given.")
        return fullpath


def set_keyframes(plugname, times, values, animtype=0):
    """
    Convinient api wrapper to set multiple keyframes.

    Args:
        plugname ([type]): [description]
        times ([type]): [description]
        values ([type]): [description]
        animtype (int, optional): [description]. Defaults to 0.
    """
    plug = api2.MSelectionList().add(plugname).getPlug(0)

    try:
        mobj = api2a.MFnAnimCurve().create(plug, animtype)
        animfn = api2a.MFnAnimCurve(mobj)
    except TypeError:
        animfn = api2a.MFnAnimCurve(plug)

    animfn.addKeys(times, pyhelper.flatten(values))


def set_cutKeys(obj, at="translate"):
    cmds.cutKey(obj, attribute=at)


def set_timeline(obj):
    times = cmds.keyframe(obj, query=True)
    try:
        time = times[0]
        cmds.currentTime(time)
    except ValueError:
        print("[ERROR] Object has no keyframes.")


def set_attribute_keyframes(values, max_range, obj, attr="rotate", animtype=0):
    """
    Convinient function to set multiple keys on a whole attribute.
    Wraps 'set_keyframes'.

    Args:
        values ([List]): [description]
        max_range ([Int]): [description]
        obj ([String]): [description]
        attr (str, optional): [description]. Defaults to "rotate".
    """

    names = ["{0}.{1}{2}".format(obj, attr, c) for c in "XYZ"]
    for n, name in enumerate(names):
        set_keyframes(name, range(max_range), values[n], animtype)


def prefix_name(name, prefix):
    """
    Prefix a name of a given node, checks if a namespace is contained and preserves it.

    Args:
        name ([String]): Name of the node.
        prefix ([String]): Prefix which should be added to the front.

    Returns:
        [String]: The new name with namespace if present.
    """
    if ":" in name:
        namespace, name = name.split(":")
        prefixName = "{0}{1}".format(prefix, name.title())
        newName = "{0}:{1}".format(namespace, prefixName)
    else:
        newName = "{0}{1}".format(prefix, name.title())

    return newName


def is_shader_equal(shader1, shader2):
    """
    Get all values of the given shaders and compare them.

    Args:
        shader1 ([String]): Name of the first shader.
        shader2 ([String]): Name of the second shader.

    Returns:
        [Bool]: Whether it is equal or not.
    """
    attrsVals1 = _get_shaderValues(shader1)
    attrsVals2 = _get_shaderValues(shader2)

    if attrsVals1 == attrsVals2:
        return True
    return False


# ----------------------- UI Helper Functions ------------------------- #
# --------------------------------------------------------------------- #


def get_imgPath():
    multFilter = """Image Files (*.jpg *.psd *.als *.dds *.gif *.cin *.iff *.exr *.png *.eps 
                *.tga *.tiff *.rla *.bmp *.xpm *.tim *.pic *.sgi *.yuv);;
                All Files (*.*)"""
    return cmds.fileDialog2(ff=multFilter, fm=1, cap="Import Image")


def get_filePath(**kwargs):
    kwargs["fm"] = 1
    if not kwargs.get("ff", None):
        kwargs["ff"] = "*"
    return cmds.fileDialog2(**kwargs)


def save_filePath(**kwargs):
    kwargs["fm"] = 0
    if not kwargs.get("ff", None):
        kwargs["ff"] = "*"
    return cmds.fileDialog2(**kwargs)


# ---------------- Context Managers and Decorators -------------------- #
# --------------------------------------------------------------------- #


@contextmanager
def undo_chunk():
    """
    Convenient Context Manager for handling Undo Chunks.
    It automatically opens and closes an UndoChunk when the code in the
    try-block is successfully run.
    """
    try:
        cmds.undoInfo(ock=True)
        yield
    finally:
        cmds.undoInfo(cck=True)


@contextmanager
def block_signals(QObj):
    """
    Convenient Context manager for blocking Qt Signals.
    Every widget change within the try-statement doens't emit it's change-Signal.

    Args:
        QObj ([QtCore.QObject]): The Object/Widget which signals should be blocked.
    """
    try:
        QObj.blockSignals(True)
        yield
    finally:
        QObj.blockSignals(False)


# ------------------------------- PLUGIN SETUP ------------------------ #
# --------------------------------------------------------------------- #


def is_plugin_loaded(plugin_name):
    return cmds.pluginInfo(plugin_name, q=True, l=True)


def reload_plugin(plugin_name, unload=False):
    if not unload:
        cmds.evalDeferred("cmds.loadPlugin('{0}')".format(plugin_name))
    else:
        cmds.evalDeferred("cmds.unloadPlugin('{0}')".format(plugin_name))


# -------------------------------- Pyside2uic ------------------------- #
# --------------------------------------------------------------------- #


def convertUi(uipath, outpath=None, outname=None):
    if not outpath:
        outpath = os.path.dirname(uipath)

    if not outname:
        outname = os.path.basename(uipath).rsplit(".", 1)[0]
        outname = "{0}.py".format(outname)

    with open(os.path.join(outpath, outname), "w") as pyfile:
        compileUi(uipath, pyfile, False, 4, False)


if __name__ == "__main__":
    # start uiconvert
    uipath = sys.argv[1]
    convertUi(uipath)
