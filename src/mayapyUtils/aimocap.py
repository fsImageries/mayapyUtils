from pprint import pprint
import torch
import numpy as np

import argparse
import pyhelper
import pathlib
import static
import json
import sys
import os


# DONT USE THIS, is going to be gone with the next update.
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
    # parser.add_argument("datapath", type=pathlib.Path,
    #                     help="Path to .npz file or output dir.")
    parser.add_argument("-r", required=True, dest="repo", type=pathlib.Path,
                        help="Path to the video-to-pose repo.")
    parser.add_argument("-i", required=True, dest="input", type=pathlib.Path,
                        help="Path to the video which should be infered.")
    parser.add_argument("-out", "--viz_output", type=pathlib.Path,
                        default=None, help="Path to which the output should be saved.")
    parser.add_argument("-det", "--detector_2d", type=str, default="alpha_pose",
                        help="Determine which 2d keypoint detector should be used.")

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


def _pose_args(repo):
    class arguments():
        # placeholder for args
        pass

    args = arguments()

    args.dataset = "h36m"
    args.keypoints = "cpn_ft_h36m_dbb"
    args.subjects_train = "S1,S5,S6,S7,S8"
    args.subjects_test = "S9,S11"
    args.subjects_unlabeled = ""
    args.actions = "*"
    args.evaluate = 'pretrained_h36m_detectron_coco.bin'
    args.checkpoint = os.path.join(repo, "checkpoint")
    args.checkpoint_frequency = 10
    args.resume = ""
    args.render = False
    args.by_subject = False
    args.export_training_curves = False
    args.stride = 1
    args.epochs = 60
    args.batch_size = 60
    args.dropout = 0.25
    args.learning_rate = 0.001
    args.lr_decay = 0.95
    args.data_augmentation = True
    args.test_time_augmentation = True
    args.architecture = "3,3,3,3,3"
    args.causal = False
    args.channels = 1024
    args.subset = 1
    args.downsample = 1
    args.warmup = 1
    args.no_eval = False
    args.dense = False
    args.disable_optimizations = False
    args.linear_projection = False
    args.bone_length_term = True
    args.no_proj = False
    args.viz_subject = None
    args.viz_action = None
    args.viz_camera = 0
    args.viz_video = None
    args.viz_skip = 0
    args.viz_output = None
    args.viz_bitrate = 30000
    args.viz_no_ground_truth = False
    args.viz_limit = -1
    args.viz_downsample = 1
    args.viz_size = 5
    args.input_npz = ""
    args.input_video = ""

    return args


# ------------------------- Videopose Inference ----------------------- #
# --------------------------------------------------------------------- #


def videpose_infer(args):
    from common.camera import normalize_screen_coordinates, camera_to_world, image_coordinates
    from common.generators import UnchunkedGenerator
    from common.model import TemporalModel
    from common.utils import Timer, evaluate, add_path
    from videopose import get_detector_2d, ckpt_time, metadata, time0

    import gene_npz

    gene_npz.args.outputpath = str(args.viz_output / "alpha_pose_kunkun_cut")
    print(gene_npz.args)
    # detector_2d = get_detector_2d(args.detector_2d)
    detector_2d = gene_npz.generate_kpts(args.detector_2d)

    assert detector_2d, 'detector_2d should be in ({alpha, hr, open}_pose)'

    # 2D kpts loads or generate
    if not args.input_npz:
        video_name = args.viz_video
        keypoints = detector_2d(video_name)
    else:
        npz = np.load(args.input_npz)
        keypoints = npz['kpts']  # (N, 17, 2)

    keypoints_symmetry = metadata['keypoints_symmetry']
    kps_left, kps_right = list(
        keypoints_symmetry[0]), list(keypoints_symmetry[1])
    joints_left, joints_right = list(
        [4, 5, 6, 11, 12, 13]), list([1, 2, 3, 14, 15, 16])

    # normlization keypoints  Suppose using the camera parameter
    keypoints = normalize_screen_coordinates(
        keypoints[..., :2], w=1000, h=1002)

    model_pos = TemporalModel(17, 2, 17, filter_widths=[3, 3, 3, 3, 3], causal=args.causal, dropout=args.dropout, channels=args.channels,
                              dense=args.dense)

    if torch.cuda.is_available():
        model_pos = model_pos.cuda()

    ckpt, time1 = ckpt_time(time0)
    print('-------------- load data spends {:.2f} seconds'.format(ckpt))

    # load trained model
    chk_filename = os.path.join(
        args.checkpoint, args.resume if args.resume else args.evaluate)
    print('Loading checkpoint', chk_filename)
    checkpoint = torch.load(
        chk_filename, map_location=lambda storage, loc: storage)  # 把loc映射到storage
    model_pos.load_state_dict(checkpoint['model_pos'])

    ckpt, time2 = ckpt_time(time1)
    print('-------------- load 3D model spends {:.2f} seconds'.format(ckpt))

    #  Receptive field: 243 frames for args.arc [3, 3, 3, 3, 3]
    receptive_field = model_pos.receptive_field()
    pad = (receptive_field - 1) // 2  # Padding on each side
    causal_shift = 0

    print('Rendering...')
    input_keypoints = keypoints.copy()
    gen = UnchunkedGenerator(None, None, [input_keypoints],
                             pad=pad, causal_shift=causal_shift, augment=args.test_time_augmentation,
                             kps_left=kps_left, kps_right=kps_right, joints_left=joints_left, joints_right=joints_right)
    prediction = evaluate(gen, model_pos, return_predictions=True)

    # save 3D joint points
    np.save(args.viz_output / "test_3d_output.npy",
            prediction, allow_pickle=True)

    rot = np.array([0.14070565, -0.15007018, -0.7552408,
                   0.62232804], dtype=np.float32)
    prediction = camera_to_world(prediction, R=rot, t=0)

    # We don't have the trajectory, but at least we can rebase the height
    prediction[:, :, 2] -= np.min(prediction[:, :, 2])
    anim_output = {'Reconstruction': prediction}
    input_keypoints = image_coordinates(
        input_keypoints[..., :2], w=1000, h=1002)

    ckpt, time3 = ckpt_time(time2)
    print(
        '-------------- generate reconstruction 3D data spends {:.2f} seconds'.format(ckpt))

    ckpt, time4 = ckpt_time(time3)
    print('total spend {:2f} second'.format(ckpt))


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
    repo = args.repo

    if args.viz_output is None:
        args.viz_output = repo / "outputs"

    pose_args = _pose_args(repo)
    pose_args.detector_2d = args.detector_2d
    pose_args.viz_output = args.viz_output
    pose_args.viz_video = args.input

    detectors = ["Alphapose", "hrnet", "openpose"]
    if str(repo) not in sys.path:
        sys.path.append(str(repo))
        for d in detectors:
            path = repo / "joints_detectors/{0}".format(d)
            sys.path.append(str(path))

    from pprint import pprint
    pprint(sys.argv)
    sys.argv = sys.argv[:1]
    # pprint(sys.path)

    videpose_infer(pose_args)

    # with open(outpath, 'w', encoding='utf-8') as f:
    # json.dump(ret, f, ensure_ascii=False,indent = 4, cls = NumpyEncoder)


if __name__ == "__main__":
    # cli()
    # exit()

    with open(sys.argv[1], "r") as f:
        data = json.load(f)

    _send_to_maya(data)

################################
# IDEA:
#   - UI for manual clean-up
#   - invert Keyframes for given range on the resulting rig
