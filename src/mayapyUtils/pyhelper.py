# pylint: disable=bare-except

from string import digits
from os.path import split, splitext    # TODO fix os import
from time import time, sleep
from contextlib import contextmanager
from PySide2 import QtCore, QtNetwork

import os
import traceback
import json
import socket

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


# ------------------------ Context Managers --------------------------- #
# --------------------------------------------------------------------- #

class FunctionTimer(object):
    def __enter__(self):
        self.start_time = time()

    def __exit__(self, *_):
        print "My program took", time() - self.start_time, "to run"


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


# --------------------- PySide2 Server/Client  ------------------------ #
# --------------------------------------------------------------------- #


class ServerBase(QtCore.QObject):

    PORT = PORT
    HEADER_SIZE = HEADER_SIZE

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

                    # -DEBUG
                    self.write({"success": True})

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


class ClientBase(object):

    PORT = PORT
    HEADER_SIZE = HEADER_SIZE

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
            self.client_socket.connect((HOST, self.port))
            self.client_socket.setblocking(0)
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

    def send(self, data):
        json_data = json.dumps(data)

        message = list()
        message.append("{0:10d}".format(len(json_data.encode())))
        message.append(json_data)

        try:
            msg_str = "".join(message)
            self.client_socket.sendall(msg_str.encode())
        except:
            traceback.print_exc()
            return None

        return self.recv()

    def recv(self):
        total_data = list()
        data = ""
        reply_length = 0
        bytes_remaining = ClientBase.HEADER_SIZE

        start_time = time()
        while time() - start_time < self.timeout:
            try:
                data = self.client_socket.recv(bytes_remaining)
            except:
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
