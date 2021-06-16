import numpy as np
import argparse
import pyhelper
import pathlib
import json
import os


VideoPoseChains = [[0, 1, 2, 3], [0, 4, 5, 6], [
    7, 8, 9, 10], [11, 12, 13], [14, 15, 16]]

Skips = [0, 7, 11, 14]

# ------------------------------ Helpers ------------------------------ #
# --------------------------------------------------------------------- #


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)


def np2json(arr, outpath):
    with open(outpath, 'w', encoding='utf-8') as f:
        json.dump(arr, f, ensure_ascii=False, indent=4, cls=NumpyEncoder)


def _get_first_search(path, ext=".npz"):
    for dirpath, _, filenames in os.walk(path):
        for filename in [f for f in filenames if f.endswith(ext)]:
            return os.path.join(dirpath, filename)


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("datapath", type=pathlib.Path,
                        help="Path to .npz file or output dir.")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-sdm", "--send_maya", action="store_true",
                       help="Send result to maya (if server is running).")
    group.add_argument("-svm", "--save_maya", action="store_true",
                       help="Save result to maya ready for maya to process.")

    return parser.parse_args()


def _send_to_maya(data):
    client = pyhelper.ClientBase()
    try:
        client.connect()
        client.send(data, json_cls=NumpyEncoder)
        print("[LOG] Successfully send rotation to maya.")
    except Exception as err:
        print("[ERROR] Error occured:\n{0}".format(err))
    finally:
        client.disconnect()


def _array_radians(arr):
    return np.radians(arr)


array_radians = np.frompyfunc(_array_radians, 1, 1)


# ---------------------------- Math Workers --------------------------- #
# --------------------------------------------------------------------- #


def get_rotation(base_p, jnt_p, parent_base_pos):
    """
    Get the rotation by calculating the angle between joints.

    Args:
        base_p ([Array]): Array containing the position of the parent joint for frame nth and nth + 1.
        jnt_p ([Array]): Array containing the position of the child joint for frame nth and nth + 1.
        parent_base_pos ([Int]): First position of the whole animation, doesn't change over time.

    Returns:
        [Array]: Array containing the Axis array and the calculated angle in degrees.
    """
    base = parent_base_pos
    base1, base2 = base_p

    p1, p2 = jnt_p

    prod1 = base - base2
    prod2 = base - base1

    v1 = base - (p1+prod2)
    v2 = base - (p2+prod1)

    length1 = np.sqrt(v1.dot(v1))
    length2 = np.sqrt(v2.dot(v2))

    if length1 == 0:
        length1 = 1
    if length2 == 0:
        length2 = 1
    base1_norm = v1 / length1
    base2_norm = v2 / length2

    p_cross = np.cross(v1, v2)
    lengthC = np.sqrt(p_cross.dot(p_cross))

    if lengthC != 0:
        axis = p_cross / lengthC
    else:
        axis = p_cross

    angle = np.arccos(base1_norm.dot(base2_norm))

    return axis, np.rad2deg(angle)


def trans2rot(base_pos, bases, joints, max_range):
    """
    Wrapper around 'get_rotation' for actual euler rotations after calculating the angles.

    Args:
        base_pos ([Int]): First position of the whole animation, doesn't change over time.
        bases ([Array]): Array containing all the parent joint positions.
        joints ([Array]): Array containing all the child joint positions.
        max_range ([Int]): Max length of the animation.

    Returns:
        [type]: [description]
    """
    rots = np.empty((max_range-1, 3), dtype=object)

    for i in range(max_range-1):
        base_positions = np.split(bases[i], 2)
        joint_positions = np.split(joints[i], 2)

        axis, angle = get_rotation(
            base_positions, joint_positions, base_pos)

        rot = axis * angle

        rots[i] = rot

    return rots


def add_rotations(rots, max_range):
    """
    Add rotations over time to get an animation.

    Args:
        rots ([Array]): Calculated rotations.
        max_range ([Int]): Max length of the animation.
        rev ([type], optional): [description]. Defaults to None.

    Returns:
        [Array]: Return the added rotations.
    """
    added_rots = np.empty((max_range-1, 3), dtype=object)

    for i in range(max_range-1):

        rot = rots[i]
        if i != 0:
            rot += rots[i-1]

        f_rot = rot

        added_rots[i] = f_rot

    return added_rots


def sub_parent_rotation(chains, active_joint, rots, max_range):
    """
    Substract parent rotations.

    Args:
        chains ([Array]): Array assembled in parent-child relation containing all rotations.
        active_joint ([Int]): Index of the active joint which should be edited.
        rots ([Array]): Array containing the rotations for the active joint.
        max_range ([Int]): Max length of the animation.

    Returns:
        [Array]: Array containing the edited rotations for the active joints.
    """
    sub_rots = np.empty((max_range-1, 3), dtype=object)

    if active_joint == 4:   # -define which rots should be used if not in order
        active_joint = 1

    for i in range(max_range-1):
        rot = rots[i]

        last_rot = chains[i, active_joint - 1]

        f_rot = rot - last_rot

        sub_rots[i] = f_rot

    return sub_rots


def post_process(rots, active_joint, max_range):
    """
    Edit specific parts of the chain.

    Args:
        rots ([Array]): Array containing the rots for the active joint.
        active_joint ([Int]): Index of the active joint which should be edited.
        max_range ([Int]): Max length of the animation.

    Returns:
        [Array]: Array containing the edited rotations.
    """
    new_rots = np.empty((max_range-1, 3), dtype=object)

    for i in range(max_range-1):

        rot = rots[i]

        if active_joint in (1, 4):  # -only legs, 1 == right leg, 4 == left leg
            mult = [0.5, 1, 1] if active_joint == 1 else [1, 0.5, 1]
            rot *= mult

        new_rots[i] = rot

    return new_rots


# ------------------------------- Mains ------------------------------- #
# --------------------------------------------------------------------- #


def go_over_chain(data):
    """
    Main function.
    I'm going over every joint and calculate the pure rotation for every joint to it's child.
    From here I'm trying to handle parenting offsets by substracting the rotation from every parent and 
    offseting values where it's necessary, eg arms, legs & neck.

    Args:
        data ([List/Array]): List containing all the positional data from VideoPose3D, shape (Framelength, 17, 3).

    Returns:
        [Array]: Returns the calculated rotations in an array with the shape (Framelength, 17, 3).
    """
    data = np.array(data)
    max_range, length, size = data.shape
    last_rots = np.empty((max_range-1, length, size), dtype=object)

    for i in range(length-1):

        base_pos = data[:, i][0]
        bases = np.column_stack((data[:-1, i], data[1:, i]))
        joints = np.column_stack((data[:-1, i+1], data[1:, i+1]))

        rotations = trans2rot(base_pos, bases, joints, max_range)
        added_rots = add_rotations(rotations, max_range)

        if i not in Skips:
            added_rots = sub_parent_rotation(
                last_rots, i, added_rots, max_range)

        final_rots = post_process(added_rots, i, max_range)

        last_rots[:, i] = final_rots

    return last_rots


def maya_process(data):
    """
    Generate maya usable array with rotations.
    Maya has a quirk, it will convert incoming roations from radians to degress which is a problem when
    you supply degrees. So I'm converting the finished results into radians and bring them in form to key
    them easly in maya.

    Args:
        data ([List/Array]): List or Array containing the calculated positional data from VideoPose.

    Returns:
        [List]: List containing the positions for every joint and the calculated rotations for every frame.
    """
    positions = [data[1][i] for i in range(17)]
    rotations = go_over_chain(data)

    key_skips = (3, 6, 10, 13, 16)

    rots_splits = []
    for idx in range(17):
        if idx in key_skips:
            rots_splits.append(None)
            continue

        idx_rots = rotations[:, idx]

        # -split array to convert it coloum-wise into radians, maya converts it automatically
        rots_split = array_radians(np.split(idx_rots, 3, axis=1))
        rots_splits.append(rots_split)

    return [positions, rots_splits]


def cli():
    """
    Simple wrapper for command line use.
    """
    args = _parse_args()
    path = args.datapath

    if not os.path.isfile(path):
        path = _get_first_search(path)

    arr = np.load(path)

    if args.send_maya or args.save_maya:
        outpath = "{}_maya_rotations.json".format(str(path).rsplit(".", 1)[0])
        ret = maya_process(arr)

        if args.send_maya:
            _send_to_maya(ret)
            return
    else:
        outpath = "{}_raw_rotations.json".format(str(path).rsplit(".", 1)[0])
        ret = go_over_chain(arr)

    with open(outpath, 'w', encoding='utf-8') as f:
        json.dump(ret, f, ensure_ascii=False,
                  indent=4, cls=NumpyEncoder)

    print("[LOG] Saved results to {0}.".format(outpath))


if __name__ == "__main__":
    cli()

################################
# IDEA:
#   - UI for manual clean-up
#   - invert Keyframes for given range on the resulting rig
