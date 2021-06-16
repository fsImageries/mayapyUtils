from string import digits
from os.path import split, splitext    # TODO fix os import
from time import time

import os


try:
    from os import scandir
except ImportError:
    try:
        from scandir import scandir
    except ImportError:
        scandir = None


# ----------------------- Static Information -------------------------- #
# --------------------------------------------------------------------- #


HOST = "localhost"
PORT = 6550
HEADER_SIZE = 10


# --------------------- Python Helper Functions ----------------------- #
# --------------------------------------------------------------------- #


def filename_from_path(filepath):
    """
    Get the file name without extension from a file path.

    Args:
        filepath ([String]): Path to desired file.

    Returns:
        [String]: File name without extension.
    """
    return os.path.splitext(os.path.basename(filepath))[0]


def basename_plus(filepath):
    """ Get every property of a filename as item """

    # Split of standard properties.
    basedir, filename = split(filepath)
    name_noext, ext = splitext(filename)

    # Split of Digits at the end of string. Useful for a name of a sequence i.e. Image Sequence.
    digitsChars = digits.encode()
    name_nodigits = name_noext.rstrip(digitsChars) if name_noext.rstrip(
        digitsChars) != name_noext else None

    return name_noext, name_nodigits, basedir, ext


def get_img_seq(filepath):
    """ Get list with all images of a chosen picture """

    # Get Filename with and without padding, Directory of the file and extension.
    _, filename_nodigits, basedir, ext = basename_plus(filepath)

    # Check if Input is part of a
    if filename_nodigits is None:
        return []

    # Scan the directory for every file that has the same Name and Extension and check if it has padding.
    # If so add to frames.
    frames = [
        f.path for f in scandir(basedir) if
        f.is_file() and
        f.name.startswith(filename_nodigits) and
        f.name.endswith(ext) and
        f.name[len(filename_nodigits):-len(ext) if ext else -1].isdigit()]

    # Check if frames has more than one Image, if so return sorted frames.
    if len(frames) > 1:
        return sorted(frames)

    return []


def get_padded_names(name, padding, sequenceLen):

    if padding == 0:
        padVal = len(str(sequenceLen))
    else:
        padVal = padding

    padding = ["%s%s" % ("0" * (padVal - len(str(num))), num)
               for num in range(0, sequenceLen)]

    final = ["%s_%s" % (name, pad) for pad in padding]

    return final


def flatten(src_list):
    """
    Basic List flattening, supports Lists, Tuples and Dictionaries.

    It checks for iter attribute and goes recursively over every item. It stores matches into a new List.
    When Dictionary it gets the items and calls itself to flatten them like a normal List.
    When no type is valid return the Item in a new List.

    Args:
        src_list ([Iterable]): The Source List which should be flattened.

    Returns:
        [List]: Returns the flattened List.
    """
    if hasattr(src_list, "__iter__"):

        if isinstance(src_list, dict):
            return flatten(src_list.items())

        flat_sum = flatten(
            src_list[0]) + (flatten(src_list[1:]) if len(src_list) > 1 else[])
        return flat_sum

    return [src_list]


def listsplit_gap(li):
    """
    Split a list by the numeric gap between it's elements. Only works on interger lists.

    Args:
        li ([List]): List which should be splited.

    Returns:
        [List]: Splited list.
    """
    # Determine where the gaps are occurring
    gap_loc = [idx + 1
               for (idx, el), next_el in zip(enumerate(li[:-1]), li[1:])
               if (next_el - el) > 1]
    # Adding beginning and end of the list
    gap_loc.insert(0, 0)
    gap_loc.append(len(li))
    # Create sublists where gaps occurs
    list_seq = [li[prev_gap:gap]
                for prev_gap, gap in zip(gap_loc[:-1], gap_loc[1:])]

    return list_seq


def join_recursive(p1, ps):
    try:
        pnew = ps[0]
        p1new = os.path.join(p1, pnew)
        ps.pop(0)
        return join_recursive(p1new, ps)
    except IndexError:
        return p1


# ------------------------ Context Managers --------------------------- #
# --------------------------------------------------------------------- #


class FunctionTimer(object):
    def __enter__(self):
        self.start_time = time()

    def __exit__(self, *_):
        print("My program took", time() - self.start_time, "to run")