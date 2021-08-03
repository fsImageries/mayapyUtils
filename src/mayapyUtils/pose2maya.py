import math
import static
import maya.cmds as cmds
import maya.OpenMaya as api

from mahelper import ServerBase, set_attribute_keyframes, getMayaWin


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


class PoseMayaServer(ServerBase):
    """
    Get VideoPose3D at https://github.com/fsImageries/video-to-pose3D.git
    Start the server in maya like this:

    if __name__ == "__main__":
        import maya.cmds as cmds
        from mayapyUtils import mahelper, pose2maya

        try:
            server.deleteLater()
        except:
            pass

        cmds.evalDeferred("server = pose2maya.PoseMayaServer(parent=mahelper.getMayaWin(),mult=1)")
    """

    def __init__(self, parent=None, importer="vp3d", mult=5, default_obj="joint"):
        super(PoseMayaServer, self).__init__(parent)

        importer_map = {
            "vp3d": VideoPose3D_Importer
        }

        self.importer = importer_map[importer]
        self.mult = mult
        self.default_obj = default_obj

    def process_data(self, data):
        importer = self.importer(mult=self.mult, default_obj=self.default_obj)
        importer.create_skeleton(data)

        self.success()

    def success(self):
        self.write({"success": True})
        print("[LOG] Successfully finished processing.")


# ------------------------ Pose Importer  ----------------------------- #
# --------------------------------------------------------------------- #


class VideoPose3D_Importer:

    def __init__(self, mult=5, default_obj="joint"):
        self.keyables = dict()
        self.group = None
        self.mult = mult
        self.pairs = static.VideoPosePairs
        self.names = static.VideoPoseNames
        self.default_obj = default_obj
        self.objs = []

    def create_skeleton(self, data):
        self.objs = [self._get_obj(i) for i in xrange(17)]
        self._prep()
        frame_length = len(data)
        print("\n[LOG] Animation length: {} frames\n".format(frame_length)),
        print("[LOG] Start processing (this can take a moment)\n"),

        # pos_keys = []
        # rot_keys = []

        def make_rad(point):
            return [math.radians(x) for x in point]

        do_print = True
        for frame, joints in enumerate(data):
            # rot_per_frame = list(xrange(17))
            for n, joint in enumerate(joints):
                obj = self.objs[n]

                try:
                    idx = 0 if n != 0 else -1
                    _, idx2 = [
                        pair for pair in self.pairs if pair[0] == n][idx]
                    p1 = joint
                    p2 = joints[idx2]

                    if do_print:
                        print("Parent={0}".format(obj))
                        print("Child={0}".format(self.objs[idx2]))
                    rot = self._get_rotation(p1, p2)

                    # if not frame == 0:
                    #     last_rot = rot_keys[frame-1][n]

                    #     rot = [cur + (last-math.radians(cur)) for last,
                    #            cur in zip(last_rot, rot)]
                    # rot_per_frame[n] = make_rad(rot)
                    cmds.xform(obj, ro=rot, ws=True)
                    # cmds.setKeyframe(obj, t=frame, v=rot[0], at='rotateX')
                    # cmds.setKeyframe(obj, t=frame, v=rot[1], at='rotateY')
                    # cmds.setKeyframe(obj, t=frame, v=rot[2], at='rotateZ')
                    cmds.setKeyframe(obj, at="rotate", t=frame+1)
                except IndexError:
                    pass
                    # rot_per_frame[n] = []

                if frame == 0:
                    mult_data = [i*self.mult for i in joint]
                    cmds.xform(obj, t=mult_data, ws=True)
                    # pos_keys.append(mult_data)
            # rot_keys.append(rot_per_frame)
            do_print = False

            if frame == 0 and self.default_obj == "joint":
                self._parenting()
            self._keying(frame)
            cmds.currentTime(cmds.currentTime(q=True)+1)

            # if frame > 100:
            #     print("Frame done: {0}/{1}\n".format(frame, frame_length)),

        # self.set_rotations(rot_keys) #TODO
        # self.set_positions(pos_keys)

        self._grouping()
        self._renaming()

        print("[LOG] Successfully imported skeleton.")

    @staticmethod
    def _get_rotation(p1, p2):
        # calc rot for 3d json
        punkt_a = api.MPoint(p1[0], p1[1], p1[2])
        punkt_b = api.MPoint(p2[0], p2[1], p2[2])
        rot_vector = punkt_a - punkt_b
        world = api.MVector(0, 1, 0)
        quat = api.MQuaternion(world, rot_vector, 1)
        mat = api.MTransformationMatrix()
        util = api.MScriptUtil()
        util.createFromDouble(0, 0, 0)
        rot_i = util.asDoublePtr()
        mat.setRotation(rot_i, api.MTransformationMatrix.kXYZ)
        mat = mat.asMatrix() * quat.asMatrix()
        quat = api.MTransformationMatrix(mat).rotation()
        m_rotation = api.MVector(math.degrees(quat.asEulerRotation().x),
                                 math.degrees(quat.asEulerRotation().y),
                                 math.degrees(quat.asEulerRotation().z)
                                 )

        return (m_rotation[0], m_rotation[1], m_rotation[2])

    @staticmethod
    def _split_rotations(rots):
        # split shape for easy keyframing
        # incoming shape:
        #   - n (frames per animation) x 17 (joints) x 3 (XYZ channels)
        # resulting shape:
        #   - 17 (joints) x 3 (XYZ channels) x n (frames per animation)
        # print(len(rots), len(rots[0]))

        rots_split = [[[] for _ in xrange(3)] for _ in xrange(17)]
        for joint_ch in rots:
            for n, jnt in enumerate(joint_ch):
                for i, d in enumerate(jnt):
                    rots_split[n][i].append(d)

        print(len(rots_split), len(rots_split[0]), len(rots_split[0][0]))
        return rots_split

    def _set_rotations(self, rots):
        rots = self._split_rotations(rots)
        rots_len = len(rots[0][0])

        for i in xrange(17):
            if not all(x == [] for x in rots[i]):
                set_attribute_keyframes(
                    rots[i], rots_len, self.objs[i], animtype=0)

    def _set_positions(self, positions):
        for i in xrange(17):
            cmds.xform(self.objs[i], t=positions[i], ws=True)

    def _set_rotations2(self, rots):
        for frame, chain in enumerate(rots):
            for j, rot in enumerate(chain):
                for attr, r in zip("ZYX", rot):
                    cmds.setKeyframe(
                        self.objs[j], at="rotate{}".format(attr), v=r, t=frame+1)

    def _keying(self, frame_id=0):
        for obj in self.keyables.values():
            cmds.setKeyframe(obj, at="translate", t=frame_id+1)
            # cmds.setKeyframe(obj, at="rotate", t=frame_id+1)

    def _grouping(self):
        if self.default_obj == "joint":
            # -objs[0] bcuz joints
            self.group = cmds.group(self.objs[0], n="skel")
        else:
            self.group = cmds.group(*self.objs, n="skel")

        cmds.xform(self.group, cp=1)
        cmds.xform(self.group, ro=(0, 0, 180))

    def _parenting(self):
        for p1, p2 in self.pairs:
            top = self.objs[p1]
            bottom = self.objs[p2]

            ls = cmds.listRelatives(top)

            if not ls:
                cmds.parent(bottom, top)
            elif bottom not in ls:
                cmds.parent(bottom, top)

    def _renaming(self):
        for k, v in self.names.items():
            obj = self.objs[k]
            ret = cmds.rename(obj, v)
            self.objs[k] = ret

    def _get_obj(self, p_id):
        if not self.keyables.get(p_id, None):
            obj = self._create_obj()
            obj = cmds.rename(obj, "{0}_pi_{1}".format(obj, p_id))
            self.keyables[p_id] = obj
            return obj
        return self.keyables[p_id]

    def _create_obj(self):

        obj = getattr(cmds, self.default_obj)()

        if not isinstance(obj, basestring):
            obj = obj[0]

        # -important to deselect as else the joints will parent the last selected object and mess up positioning
        cmds.select(cl=True)
        return obj

    def _prep(self):
        cmds.select(cl=True)
        cmds.currentTime(1)


class VideoPose3D_Skeleton:

    def __init__(self, mult=5):
        self.pairs = sorted(static.VideoPosePairs)
        self.mult = mult
        self.jnts = []
        self.jnts_proj = []
        self.drivers = []

    def create(self, data, suffix="vp3d"):
        self.frames = len(data)
        self._skeleton(data, suffix)

        self._parenting()
        # self._parenting(proj=True)
        self._parenting(drivers=True, grp=True)

        self._orientate()

    @staticmethod
    def _get_rotation(p1, p2):
        # calc rot for 3d json
        punkt_a = api.MPoint(p1[0], p1[1], p1[2])
        punkt_b = api.MPoint(p2[0], p2[1], p2[2])
        rot_vector = punkt_a - punkt_b
        world = api.MVector(0, 1, 0)
        quat = api.MQuaternion(world, rot_vector, 1)
        mat = api.MTransformationMatrix()
        util = api.MScriptUtil()
        util.createFromDouble(0, 0, 0)
        rot_i = util.asDoublePtr()
        mat.setRotation(rot_i, api.MTransformationMatrix.kXYZ)
        mat = mat.asMatrix() * quat.asMatrix()
        quat = api.MTransformationMatrix(mat).rotation()
        m_rotation = api.MVector(math.degrees(quat.asEulerRotation().x),
                                 math.degrees(quat.asEulerRotation().y),
                                 math.degrees(quat.asEulerRotation().z)
                                 )

        return (m_rotation[0], m_rotation[1], m_rotation[2])

    def _jnt_lookup(self, idx, proj=False, drivers=False):
        if proj:
            jnts = self.jnts_proj
        elif drivers:
            jnts = self.drivers
        else:
            jnts = self.jnts

        for i in jnts:
            name_num = i.rsplit("_", 2)[1]
            if int(name_num) == idx:
                return i

    def _skeleton(self, data, suffix="vp3d"):
        if not cmds.objExists("drivers_{0}".format(suffix)):
            cmds.group(n="drivers_{0}".format(suffix), em=True)

        for frame, jnt in enumerate(data):
            if not cmds.objExists("anim_joint"):
                cmds.group(n="anim_joint", em=True)
                # anim_grp_prj = cmds.group(n="anim_joint_2d", em=True)
                # cmds.parent(anim_grp_prj, "anim_joint")

            for jnt_id, trans in enumerate(jnt):
                trans = [i*self.mult for i in trans]
                if not cmds.objExists("anim_jnt_driver_{0}_{1}".format(jnt_id, suffix)):
                    cmds.select(clear=True)
                    jnt = cmds.joint(n="jnt_{0}_{1}".format(
                        jnt_id, suffix), relative=True)
                    self.jnts.append(jnt)
                    # cmds.setAttr("{0}.radius".format(jnt), 10)
                    # cmds.setAttr("{0}.displayLocalAxis".format(jnt), 1)

                    # match same pos for first frame
                    # print(trans[0], trans[1], trans[2], "\n"),
                    cmds.move(trans[0], trans[1], trans[2], jnt)

                    anim_grp_child = cmds.listRelatives(
                        "anim_joint", children=True) or []
                    if not jnt in anim_grp_child:
                        cmds.parent(jnt, "anim_joint")

                    # create 2d projection
                    # jnt_proj = cmds.duplicate(
                    #     jnt, n="jnt_{0}_proj".format(jnt_id))
                    # self.jnts_proj.append(jnt_proj[0])

                    # cmds.pointConstraint(jnt, jnt_proj, mo=False, skip="z")
                    # cmds.setAttr("{0}.translateZ".format(jnt_proj[0]), 0)
                    # cmds.parent(jnt_proj, "anim_joint_2d")

                    # driver locator
                    driver = cmds.spaceLocator(
                        n="anim_jnt_driver_{0}_{1}".format(jnt_id, suffix))
                    # drive jnt with animated locator frim frame 0
                    cmds.pointConstraint(driver, jnt)
                    # if not driver in cmds.listRelatives("drivers_{0}".format(suffix), children=True) or []:
                    cmds.parent(driver, "drivers_{0}".format(suffix))
                    self.drivers.append(driver[0])

                # add trans anim values to driver locator
                cmds.setKeyframe("anim_jnt_driver_{0}_{1}".format(
                    jnt_id, suffix), t=frame, v=trans[0], at='translateX')
                cmds.setKeyframe("anim_jnt_driver_{0}_{1}".format(
                    jnt_id, suffix), t=frame, v=trans[1], at='translateY')
                cmds.setKeyframe("anim_jnt_driver_{0}_{1}".format(
                    jnt_id, suffix), t=frame, v=trans[2], at='translateZ')

        # hacking 3d-pose-baseline coord. to maya
        cmds.setAttr("drivers_{0}.rotateX".format(suffix), -180)

    def _parenting(self, proj=False, drivers=False, grp=False):
        for p1, p2 in self.pairs:
            top = self._jnt_lookup(p1, proj=proj, drivers=drivers)
            bottom = self._jnt_lookup(p2, proj=proj, drivers=drivers)

            ls = cmds.listRelatives(top)

            if not ls or bottom not in ls:
                if not grp:
                    cmds.parent(bottom, top)
                else:
                    b_name = "{0}_ctrl_grp".format(bottom)
                    bottom = cmds.group(bottom, n="{0}_ctrl_grp".format(
                        bottom)) if not cmds.objExists(b_name) else b_name

                    t_name = "{0}_ctrl_grp".format(top)
                    top = cmds.group(top, n="{0}_ctrl_grp".format(
                        top)) if not cmds.objExists(t_name) else t_name
                    cmds.parent(bottom, top)

    def _orientate(self):
        skips = [0, 7, 8, 9, 10]
        for frame in xrange(self.frames):
            for j1, j2 in self.pairs:
                if j1 in skips:
                    continue

                parent_jnt = self._jnt_lookup(j1)
                child_jnt = self._jnt_lookup(j2)

                p1 = cmds.xform(parent_jnt, q=True, t=True, ws=True)
                p2 = cmds.xform(child_jnt, q=True, t=True, ws=True)

                rotation = self._get_rotation(p1, p2)
                cmds.setKeyframe(parent_jnt, t=frame,
                                 v=rotation[0], at='rotateX')
                cmds.setKeyframe(parent_jnt, t=frame,
                                 v=rotation[1], at='rotateY')
                cmds.setKeyframe(parent_jnt, t=frame,
                                 v=rotation[2], at='rotateZ')
