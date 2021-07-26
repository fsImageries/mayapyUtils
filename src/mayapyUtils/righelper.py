import maya.cmds as cmds
import math
import json
import mahelper
import pose2maya
from pyUtils import pyhelper
# TODO change list comprehensions to pass pure lists into commands as they are designed that way :/


# ---------------------------- Helpers -------------------------------- #
# --------------------------------------------------------------------- #


def joint_search(a_jnts, jnt_ids):
    """
    Search  a joint based on it's numeric value given by it's name.
    Only works if given joints are numerically named.

    Args:
        a_jnts ([List]): All joints in which to look for.
        jnt_ids ([List]): List containing ints contained by the joints.

    Returns:
        [List]: Found joints, empty if nothing found.
    """
    res = []
    for idx in jnt_ids:
        for n, jnt in enumerate(a_jnts):
            if "|" in jnt:
                jnt = jnt.rsplit("|")[-1]

            if str(idx) == ''.join(filter(str.isdigit, str(jnt))):
                res.append(a_jnts[n])
    return res


def move_keyframes(top_parent, mv=5):
    """
    Move keyframes for given node and all children by the given amount in frames.

    Args:
        top_parent ([Str]): Name of the top most node.
        mv (Int, optional): The amount by which it should be moved, given in frames. Defaults to 5.
    """
    all_jnts = cmds.listRelatives(top_parent, ad=True, f=True)
    all_jnts.append(top_parent)

    for jnt in all_jnts:
        anims = cmds.listConnections(jnt, t="animCurve")

        if anims:
            for anim in anims:
                cmds.keyframe(anim, edit=True, relative=True, timeChange=mv)


def import_videopose(path):
    """
    Import 3d points of a VideoPose3D inference given in .Json.

    Args:
        path ([Str]): Path to .Json file.

    Returns:
        [mahelper.VideoPose_Importer]: Importer class which holds the relevant information.
    """
    with open(path, "r") as f:
        data = json.load(f)

    pose = pose2maya.VideoPose3D_Importer()
    pose.create_skeleton(data)
    return pose


# ------------------------- Rig 'T-Posing' ---------------------------- #
# --------------------------------------------------------------------- #


def center_chain_transform(ch_trans, top_jnt):
    """
    Center the transform by positioning the pivot at the top most joints position and moving it back to scenes nullpoint.

    Args:
        ch_trans ([Str]): Group transform containing the skeleton.
        top_jnt ([Str]): Top most joint under the skeleton.
    """
    x, y, z = cmds.xform(top_jnt, q=True, t=True, ws=True)

    cmds.move(x, y, z, "{0}.scalePivot".format(ch_trans),
              "{0}.rotatePivot".format(ch_trans), absolute=True)

    cmds.xform(ch_trans, q=True, t=True, os=True)
    cmds.xform(ch_trans, t=(0, 0, 0), os=True)


# all except head joints

def all_jnts_pose(jnts):
    """
    Zero out Z value of all joints. 

    Args:
        jnts ([List]): List containing the str names of the joints.
    """
    for jnt in jnts:
        x, y, z = cmds.xform(jnt, q=True, t=True)
        cmds.xform(jnt, t=[x, y, 0])


# only top leg joints

def leg_jnts_pose(leg_jnts):
    """
    Zero the Y value of the top leg joints and the X value of all subsequent children.

    Args:
        leg_jnts ([List]): List containing the str names of the joints.
    """
    for leg_jnt in leg_jnts:
        all_jnts = cmds.listRelatives(leg_jnt, ad=True, f=True)
        all_jnts.append(leg_jnt)

        for jnt in all_jnts:
            x, y, z = cmds.xform(jnt, q=True, t=True)

            if jnt == leg_jnt:
                cmds.xform(jnt, t=[x, 0, z])
            else:
                cmds.xform(jnt, t=[0, y, z])


# only spine joints

def spine_jnts_pose(spine_jnts):
    """
    Zero the X value of the spine joints.

    Args:
        spine_jnts ([List]): List containing the str names of the joints.
    """
    for spine in spine_jnts:
        x, y, z = cmds.xform(spine, q=True, t=True)
        cmds.xform(spine, t=[0, y, z])


# only first 2 top arm joints

def arm_jnts_pose(arm_jnts, clean=True):
    """
    Try to pose the arm joints by drawing a curve in 45 degree
    and snaping the arm joints to the nearest position on the curve.

    Args:
        arm_jnts ([List]): List containing the top most arm joints.
        clean (Bool, optional): If True delete the resulting curves. Defaults to True.
    """
    dels = []

    for top_jnt in arm_jnts:

        jnt_pos = cmds.xform(top_jnt, q=True, t=True, ws=True)
        end_pos = [jnt_pos[0]*4, jnt_pos[1]/4, jnt_pos[2]]

        crv = cmds.curve(p=[end_pos, jnt_pos], d=1)
        childs = cmds.listRelatives(top_jnt, ad=True, f=True)

        if clean:
            dels.append(crv)

        for tar_jnt in sorted(childs):
            tar_pnt = cmds.xform(tar_jnt, q=True, t=True, ws=True)
            near_pos = get_nearestPoint(crv, tar_pnt)

            cmds.xform(tar_jnt, t=near_pos, ws=True)

    if dels:
        [cmds.delete(d) for d in dels]


def get_nearestPoint(curve, pnt, near_nd=None, clean=True):
    """
    Create a 'nearestPointOnCurve' node and plug in the given curve and source position.

    Args:
        curve ([Str]): The curve to look for points.
        pnt ([List]): Vector3 List containing the source point from which to look, in WorldSpace.
        near_nd ([Str], optional): Supply when a 'nearestPointOnCurve' node already exists thats should be used. 
        Defaults to None.
        clean (Bool, optional): If True delete all created nodes. Defaults to True.

    Returns:
        [List]: Vector3 List containing the found position.
    """
    if not near_nd:
        near_nd = cmds.createNode("nearestPointOnCurve")

    cmds.setAttr("{0}.inPosition".format(near_nd), pnt[0], pnt[1], pnt[2])
    cmds.connectAttr("{0}.worldSpace[0]".format(
        curve), "{0}.inputCurve".format(near_nd))

    ret = cmds.getAttr("{0}.position".format(near_nd))[0]

    if clean:
        cmds.delete(near_nd)

    return ret


# only joints with same amount of children

def mirror_jnts(first, second):
    """
    Mirror a joint chain around the X position, chains need to have the same amount of children.

    Args:
        first ([Str]): Source joint which should be applied.
        second ([Str]): Target joint which should be mirrored.
    """
    childs = cmds.listRelatives(first, c=True, f=True)
    childs_sec = cmds.listRelatives(second, c=True, f=True)
    if childs:
        mirror_jnts(childs[0], childs_sec[0] if childs_sec else second)

    # base case
    first_pos = cmds.xform(first, q=True, t=True)
    first_pos[0] *= -1
    cmds.xform(second, t=first_pos)


# only joints in pairs, should be parent and child joints
# scale arm joints to rest-length

def get_dist(vec1, vec2):
    """
    Get distance between to vectors.

    Args:
        vec1 ([List]): Vector3 List.
        vec2 ([type]): Vector3 List.

    Returns:
        [Float]: Found distance.
    """
    vec_sub = [vec1[0] - vec2[0], vec1[1] - vec2[1], vec1[2] - vec2[2]]
    vec_pow = [s**2 for s in vec_sub]

    return math.sqrt(sum(vec_pow))


def get_max_dist(first, second, t_range):
    """
    Find the longest distance between to objects over time.

    Args:
        first ([Str]): Start object.
        second ([Str]): End object.
        t_range ([Int]): The range in which to check the distance.

    Returns:
        [Float]: Found distance.
    """
    dists = []
    t_og = cmds.currentTime(q=True)
    for _ in range(int(t_range)):
        vec1 = cmds.xform(first, q=True, t=True, ws=True)
        vec2 = cmds.xform(second, q=True, t=True, ws=True)

        dist = get_dist(vec1, vec2)
        dists.append(dist)
        cmds.currentTime(cmds.currentTime(q=True)+1)

    cmds.currentTime(t_og)

    return max(dists)


def scale_vec_distance(vec1, vec2, dist):
    """
    Move vector by distance in it's pointing direction.

    Args:
        vec1 ([List]): Vector3 List.
        vec2 ([List]): Vector3 List.
        dist ([Float]): Distance by which it should be moved.

    Returns:
        [List]: Vector3 List containing the new position for vec2.
    """
    heading = [vec1[0] - vec2[0], vec1[1] - vec2[1], vec1[2] - vec2[2]]
    distance = get_dist(vec1, vec2)

    # direction = heading / distance
    direction = [(1/distance) * s for s in heading]
    direction = [d*-1 for d in direction]

    return [p + (direction[n] * dist) for n, p in enumerate(vec1)]


def rest_length(first, second, t_range):
    """
    Scale the joints, in it's pointing direction, by the longest distance the rig will reach.
    It goes over keys applied on the joints and keeps track of the furthes distance they reach,
    after that it will move the joints to reach that distance. 
    Used to apply correct Ik-Handles which don't understretch.

    Args:
        first ([Str]): Start object.
        second ([Str]): End object.
        t_range ([Int]): The range in which to check.

    Returns:
        [List]: Vector3 List containing the new position for the second object.
    """
    vec1 = cmds.xform(first, q=True, t=True, ws=True)
    vec2 = cmds.xform(second, q=True, t=True, ws=True)

    dist = get_max_dist(first, second, t_range)
    sc_pos = scale_vec_distance(vec1, vec2, dist)

    cmds.xform(second, t=sc_pos, ws=True)
    cmds.setKeyframe(second, at="translate")

    return sc_pos


# ------------------------- Ik-ing skeleton --------------------------- #
# --------------------------------------------------------------------- #


def make_src_tar(src_skel, src_name=None, dup_name=None):
    """
    Simple duplicateSpecial wrapper, you only have to select the top most tranform. It will duplicate everything
    downstream.
    You can supply a src and target name for the original and duplicated object.
    Used for Ik-transfer tools to create a src and target group for constraining.

    Args:
        src_skel ([Str]): Top most transform containing the skeleton.
        src_name ([Str], optional): New name for src_skel. Defaults to None.
        dup_name ([Str], optional): New name for duplicated skel. Defaults to None.

    Returns:
        [Tuple]: The new src_skel- and duplicated skel name.
    """
    dup_skel = cmds.duplicate(src_skel, un=True)[0]

    src_name = src_name if src_name else "{0}_src".format(src_skel)
    src_skel = cmds.rename(src_skel, src_name)

    if dup_name:
        dup_skel = cmds.rename(dup_skel, dup_name)

    return src_skel, dup_skel


def ik_transfer(first, second, src_jnt, pole_jnt):
    """
    Creates a simple Ik-Handle (RotatePlaneSolver) used for appendices, eg. arms and legs, which gets contrained to the given src transforms.
    The src_jnt drives the resulting ik handle and should be positioned at resulting end of the ik chain.
    The polevec_jnt drives the pole vector of the ik chain and should be positioned accordingly. 
    They're named joints but can be everything that is a transform.

    Args:
        first ([Str]): Start joint.
        second ([Str]): End joint.
        src_jnt ([Str]): Src joint to drive Ik-Handle.
        pole_jnt ([Str]): Src joint to drive poleVector.
    """
    # create ik handle
    handle, effector = cmds.ikHandle(sj=first, ee=second)

    # contraint source handle to source joint
    cmds.parentConstraint(src_jnt, handle, mo=True)
    cmds.poleVectorConstraint(pole_jnt, handle)


def ikSpline_transfer(first, second, up_src_jnt, low_src_jnt):
    """
    Create a spline Ik-Handle with the Ik-SplineHandleTool from the supplied spine joints.
    It will create 2 cluster paired to the cvs of the driving crv, these clusters will get contrained 
    to the given src_jnts. One for the upper cluster and one for the lower.

    Args:
        irst ([Str]): Start joint.
        second ([Str]): End joint.
        up_src_jnt ([Str]): Src joint to drive upper cluster.
        low_src_jnt ([Str]): Src joint to drive lower cluster.
    """
    # create ik spline handle
    res = cmds.ikHandle(sj=first, ee=second,
                        sol="ikSplineSolver", pcv=False, ns=4)
    sp_handle, sp_effector, sp_curve = res

    deg = cmds.getAttr('{0}.degree'.format(sp_curve))
    spans = cmds.getAttr('{0}.spans'.format(sp_curve))

    cmds.select("{0}.cv[0:{1}]".format(sp_curve, deg))
    cmds.select("{0}.cv[{1}:]".format(sp_curve, spans))

    # create cluster for upper and lower region
    low_cl_name, low_cl_handle = cmds.cluster(
        "{0}.cv[0:{1}]".format(sp_curve, deg))
    up_cl_name, up_cl_handle = cmds.cluster(
        "{0}.cv[{1}:]".format(sp_curve, spans))

    # contraint ik spline to joints
    for jnt, hndl in [(up_src_jnt, up_cl_handle), (low_src_jnt, low_cl_handle)]:
        cmds.parentConstraint(jnt, hndl, mo=True)

    cmds.parentConstraint(up_src_jnt, up_cl_handle, mo=True)
    cmds.parentConstraint(low_src_jnt, low_cl_handle, mo=True)


# ------------------------------ Misc --------------------------------- #
# --------------------------------------------------------------------- #


def loc_transformer(src_jnt):
    """
    Creates a locator which will be paired to the incoming connections of the joint.
    The locator will get zerod on the joint position and its position add to the incoming values.
    It's used to transform already animated joints without working around keyframes.
    Use the remove function to establish the original connections.

    Args:
        src_jnt ([Str]): Joint to transform.
    """
    loc = cmds.spaceLocator(n="{0}_translater".format(src_jnt))[0]

    # invert X & Y values of loc
    loc_mult_name = "{0}_mult".format(loc)
    loc_mult = cmds.shadingNode(
        "multiplyDivide", asUtility=True, n=loc_mult_name)
    cmds.setAttr("{0}.input2".format(loc_mult), -1, -1, 1)

    for c in "YXZ":
        cmds.connectAttr("{0}.translate{1}".format(loc, c),
                         "{0}.input1.input1{1}".format(loc_mult, c))

    src_pos = cmds.xform(src_jnt, q=True, t=True, ws=True)
    cmds.xform(loc, t=src_pos, ws=True)

    cmds.makeIdentity(loc, apply=True, t=1, r=1, s=1, n=0)  # freeze transforms

    # link joint anims to transformer
    conns = cmds.listConnections(src_jnt, c=True, d=False, p=True)
    conn_pairs = [[i, conns[n+1]]
                  for n, i in enumerate(conns) if n % 2 == 0 if "translate" in i]

    for dst, src in conn_pairs:
        add_name = "{0}_add".format(dst.split(".")[0])
        add_linear = cmds.shadingNode(
            "addDoubleLinear", asUtility=True, n=add_name)

        # Connect anim curve to add_double_linear
        cmds.connectAttr(src, "{0}.input1".format(add_linear))
        # Connect mult_div to add_double linear
        cmds.connectAttr("{0}.output.output{1}".format(
            loc_mult, dst[-1]), "{0}.input2".format(add_linear))
        # Connect add_double_linear to joint
        cmds.connectAttr("{0}.output".format(add_linear), dst, force=True)


def remove_loc_transformer(loc):
    """
    Removes the connected location by going upstream from the locator node.

    Args:
        loc ([Str]): Locator transform connected to a joint.
    """
    mult = next(i for i in cmds.listConnections(loc, s=False) if "mult" in i)
    adds = [i for i in cmds.listConnections(mult, s=False) if "add" in i]
    jnt = next(i for i in cmds.listConnections(
        adds[0], s=False) if cmds.objectType(i) == "joint")

    conns = cmds.listConnections(jnt, c=True, d=False, p=True)
    trans = [i for n, i in enumerate(conns) if n % 2 == 0 if "translate" in i]
    anims = [cmds.listConnections("{0}.input1".format(src), p=True)[
        0] for src in adds]

    for src, dst in zip(anims, trans):
        cmds.connectAttr(src, dst, force=True)

    for i in adds+[mult, loc]:
        cmds.delete(i)


def export_ma_cam(cam_og=None, save=True, mult=None, locs=True):
    """
    Export a selected or given camera to something After Effects can understand.
    We first copy the camera at the start position, without keys or inputs.
    Then we constraint the original camera to the duplicate.
    We bake out the positions and save the selection to new .ma file.

    On the way we can multiply the values to scale the camera for AE.
    We can also generate locators on the path of the camera and export those as nulls.

    Args:
        cam_og ([Str], optional): The name of the camera node. Use selection when not supplied. Defaults to None.
        save ([Bool], optional): Export the created nodes, deletes the exported nodes when true. Defaults to True.
        mult ([Int], optional): The values by which the camera values gets multiplied. Defaults to None.
        locs ([Bool], optional): Generate and export locators on the camera path if true. Defaults to True.
    """

    if not cam_og:
        cam_og = cmds.ls(sl=True, l=True)

    keytimes = cmds.keyframe(cam_og, q=True)
    start, end = min(keytimes), max(keytimes)

    cam_dup = cmds.duplicate(cam_og)

    if str(cmds.ls(cam_dup, l=True)).count("|") >= 2:
        cam_dup = cmds.parent(cam_dup, world=True)

    constraint = cmds.parentConstraint(cam_og, cam_dup)
    cmds.bakeResults(cam_dup, simulation=True, t=(start, end))
    cmds.delete(constraint)

    anims = unchanging_animCurves(
        cam_dup+cmds.listRelatives(cam_dup, shapes=True))
    for nd, _ in anims:
        cmds.delete(nd)

    if mult:
        mult_keyframes(cam_dup, mult=mult)

    if locs:
        locs = loc_over_time(cam_dup[0])
        cmds.select(cam_dup+locs)

    if save:
        outpath = mahelper.save_filePath(ff="*.ma")
        if outpath:
            cmds.file(outpath, force=True, options="v=0",
                      typ="mayaAscii", es=True)
            dels = cam_dup+locs if locs else cam_dup
            cmds.delete(dels)


def mult_keyframes(nodes, mult=100):
    """
    Multiply all keyframes by the given value.

    Args:
        nodes ([Str,List]): Name of the nodes on which to work, also works with list of names.
        mult ([Int], optional): The multiplication value. Defaults to 100.
    """
    anims = cmds.keyframe(nodes, q=True, n=True)
    keys = cmds.keyframe(nodes, q=True, vc=True, tc=True)
    frac = len(keys)/len(anims)

    keys = [keys[frac*i:frac*(i+1)] for i in range(len(anims))]
    keys = [[k[i:i+2] for i in range(len(k)) if i % 2 == 0] for k in keys]

    for nd, data in zip(anims, keys):

        for vals in data:
            time, val = vals
            val *= mult

            cmds.setKeyframe(nd, v=val, t=time)


def loc_over_time(node):
    """
    Generate a locator at the start, mid and end position of the given node in it's keyrange.

    Args:
        node ([Str]): Name of the node on which to work.

    Returns:
        [List]: Names of the generated locators.
    """

    keys = cmds.keyframe(node, q=True)
    indices = min(keys), max(keys)/2, max(keys)

    pos = [pyhelper.flatten(cmds.getAttr(
        "{0}.translate".format(node), t=idx)) for idx in indices]
    pos = [[0, 0, 0]] + pos  # add Zero-origin as locator

    def name(x): return "NULL_{0}".format(x)

    locs = pyhelper.flatten([cmds.spaceLocator(n=name(n))
                            for n in range(len(pos))])
    [cmds.xform(loc, t=p) for loc, p in zip(locs, pos)]

    return locs

# ---------------------------- Keyframes ------------------------------ #
# --------------------------------------------------------------------- #


def unchanging_animCurves(nodes):
    """
    Find unchanging keyframes on the selected objects.

    Args:
        nodes ([List]): List containing the nodes to check.

    Returns:
        [List]: List of pairs containing the animation curve and unchanging value.
    """
    conns = [cmds.listConnections(s, t="animCurve") for s in nodes]
    anims = pyhelper.flatten(conns)

    def get_set(x): return {val for val in cmds.keyframe(x, q=True, vc=True)}
    def check(x): return len(get_set(x)) == 1
    unchanged = [[anim, get_set(anim).pop()]
                 for anim in anims if anim and check(anim)]

    return unchanged


def get_key_ranges(keys):
    """
    Get ranges based on length of unchanging values.

    Args:
        keys ([List]): List containing Time, Keyvalue of a single animation curve.

    Returns:
        [List]: List containing dictionaries with time and value changes.
    """
    ranges = []
    last = None

    for n, val in enumerate(keys):
        t, k = val
        if n == len(keys)-1:
            ranges.append(add)
            continue

        if last != k:
            if last is not None:
                ranges.append(add)
            last = k
            add = {
                "time": t,
                "val": k
            }
        else:
            add["time"] = t
            add["val"] = k

    return ranges


def get_keyframe_len(keys, cur_range):
    """
    Get the num of actual keyed keyframes, so that a range that only has 2 frames doesn't get chosen for display.

    Args:
        keys ([List]): List containing all keys, with time, keyvalue.
        cur_range ([Dict]): Dictionary containing the time and keyvalue for the current range.

    Returns:
        [Int]: Length of the resulting list of indices.
    """
    cur_idx = keys.index([cur_range["time"], cur_range["val"]])
    try:
        srt = list(i for i in range(len(keys))
                   if keys[i][1] == cur_range["val"] and i < cur_idx)
        srt = min(pyhelper.listsplit_gap(srt)[-1])
    except (StopIteration, ValueError):
        return 0

    return len(keys[srt:cur_idx+1])


def unchanging_ranges(nodes):
    """
    Find unchanging periods of time for keyframes on the given nodes.

    Args:
        nodes ([List]): List containing nodes which should be checked.

    Returns:
        [List]: List containing the node and lists of ranges (start idx, end idx) of unchanging values.
    """
    anims = [cmds.listConnections(n, t="animCurve") for n in nodes]
    anims = pyhelper.flatten(anims)

    anim_ranges = []
    for anim in anims:
        if not anim:
            continue

        keys = cmds.keyframe(anim, q=True, vc=True, tc=True)
        keys = [[v, keys[n+1]] for n, v in enumerate(keys) if n % 2 == 0]

        ranges = get_key_ranges(keys)

        key_ranges = []
        for n, r in enumerate(ranges):
            # find num of keys in range
            if get_keyframe_len(keys, r) <= 2:
                continue

            start = ranges[n-1]["time"] + 1 if n != 0 else 1
            end = r["time"]

            diff = end - start
            if diff >= 2:
                #cmds.cutKey(node, time=(start+1, end-1), clear=True)
                # key_ranges.append(int(start + 1))
                # key_ranges.append(int(end - 1))
                key_ranges.append((int(start + 1), int(end - 1)))

        if key_ranges:
            anim_ranges.append([anim, key_ranges])

    return anim_ranges
