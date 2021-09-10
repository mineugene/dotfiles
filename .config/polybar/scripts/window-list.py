#!/usr/bin/env python

import argparse
import os
import pathlib
import signal
import stat
import subprocess
import sys
import typing


class Node(object):
    """Represents a node with an attached window.
    :param kwargs: Dictionary of columns from wmctrl line
    """

    def __init__(self, **kwargs):
        """Contructor method
        """
        self.id = kwargs.get("id")
        self.desktop_id = kwargs.get("desktop")
        self.pid = kwargs.get("pid")
        self.geometry = kwargs.get("geometry")
        self.app_name = kwargs.get("class")
        self.win_name = kwargs.get("title")

    @property
    def attrs(self) -> dict:
        return {
            "id": self.id,
            "desktop": self.desktop_id,
            "pid": self.pid,
            "geometry": self.geometry,
            "class": self.app_name,
            "title": self.win_name
        }

    @attrs.setter
    def attrs(self, info: dict):
        new_node = Node(
            id=info["id"],
            desktop_id=info["desktop"],
            pid=info["pid"],
            geometry=info["geometry"],
            app_name=info["class"],
            win_name=info["title"]
        )
        return new_node


class EventListener(object):
    """Subscribes to bspwm events using 'bspc subscribe'.
    """
    EVENTS = [
        "desktop_focus",
        "desktop_layout",
        "node_focus",
        "node_remove",
    ]

    @classmethod
    def start(cls) -> typing.Iterator[str]:
        """A generator for triggered events that 'bspc subscribe' observes

        :return: Representation of event (see 'man bspc' for event format)
        :raises CalledProcessError: Non-zero return code and the signal
        """
        cmd = "bspc subscribe".split()
        cmd.extend(cls.EVENTS)
        event_pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
        for event in iter(event_pipe.stdout.readline, ""):
            yield event  # events from captured stdout of bspc subscribe

        event_pipe.stdout.close()
        ret_code = event_pipe.wait()  # determine exit status and report fails
        raise subprocess.CalledProcessError(ret_code, cmd)


class NodeDriver(object):
    """Queries the state of bspwm nodes using 'bspc query'.
    """

    def _map_hex_id(self, node_id: str) -> int:
        """A query output is typically in hex (0x..) format; therefore,
        it is mapped into int for ease of comparison

        :param node_id: The id number of node in base-16 str
        :return: Node id in base-10 int
        """
        if node_id == "":
            return 0
        return int(node_id, 16)

    def _map_node_query(self, output: list) -> list:
        """Maps the lines of hex node id from a query

        :param output: Lines from query output
        :return: List of node id in base-10 integer
        """
        return list(map(self._map_hex_id, output))

    def query_focused(self) -> int:
        """Queries the currently focused node id in base-10
        :return: Focused node id in base-10 integer
        """
        cmd = "bspc query -N -n focused".split()
        pipe = subprocess.run(cmd, capture_output=True, text=True)
        node_focused_id = self._map_node_query(
            pipe.stdout.rstrip().split("\n")
        )
        return node_focused_id.pop()

    def query_active_windows(self) -> list:
        """Queries a list of nodes in the reference desktop that contain an
        attached window

        :return: List of node id in reference desktop in base-10 integer
        """
        cmd = "bspc query -N -n .local.window".split()
        pipe = subprocess.run(cmd, capture_output=True, text=True)
        node_win_id = self._map_node_query(pipe.stdout.rstrip().split("\n"))
        return node_win_id


class WindowInfoDriver(object):
    """Retrieves window information for all windows using 'wmctrl'.
    """

    def _map_wmctrl_line(self, line: str) -> dict:
        """Maps lines from 'wmctrl' into a dictionary of each column

        :param line: A line from 'wmctrl' list output
        :return: Hashed column names with its values
        """
        if line == "":
            return {}
        # filter out redundant whitespace special characters
        wminfo = " ".join(line.split()).encode("ascii", errors="ignore")
        # parse columns
        wminfo = wminfo.decode().split(" ", 9)
        return {
            "id": int(wminfo[0], 0),
            "desktop": int(wminfo[1]),
            "pid": int(wminfo[2]),
            "geometry": list(map(int, wminfo[3:7])),
            "class": wminfo[7].split(".")[-1].lower(),
            # filter out non-alphanumeric characters
            "title": " ".join(wminfo[9].split())
        }

    def get_info_map(self) -> dict:
        """Retrieves info from all windows
        :return: Hashed window ids with its properties
        """
        cmd = "wmctrl -pGxl".split()
        pipe = subprocess.run(cmd, capture_output=True, text=True)

        result = {}
        for line in pipe.stdout.rstrip().split("\n"):
            tokenized_line = self._map_wmctrl_line(line)
            if "id" not in tokenized_line:
                continue
            id = tokenized_line.pop("id", 0)  # extract window id
            result[id] = tokenized_line  # key: window id, value: props
        return result


class WindowListRepo(object):
    """A repository of nodes with attached windows in the reference desktop.

    :param node_driver: Driver for querying the bspwm state
    :param wminfo_driver: Driver for fetching window information
    """

    def __init__(
        self, node_driver: NodeDriver, wminfo_driver: WindowInfoDriver
    ):
        """Constructor method
        """
        self._d_node = node_driver
        self._d_wminfo = wminfo_driver

    def get_window_list(self) -> list:
        """Gets a list of windows and its properties, matching the description
        from :class:`Node`

        :return: List of nodes and their window properties
        """
        node_win_id = self._d_node.query_active_windows()
        wminfo_hash = self._d_wminfo.get_info_map()

        result = []
        if not node_win_id or node_win_id[-1] == 0:
            return result
        for id in node_win_id:
            node = Node(id=id, **wminfo_hash[id])
            result.append(node.attrs)
        return result

    def get_focused_window(self) -> dict:
        """Gets the window properties of the currently focused window. The dict
        keys match the description from :class:`Node`

        :return: Window properties of the focused node
        """
        node_focused = self._d_node.query_focused()
        wminfo_hash = self._d_wminfo.get_info_map()

        if node_focused == 0:
            return {}
        return Node(id=node_focused, **wminfo_hash[node_focused]).attrs


class WindowInfoFormatter(object):
    """Window title formatter by string interpolation for polybar module.
    """
    # window label size
    LABEL_SIZE = 20  # required - greater than or equal to len(OVERFLOW)+1
    # colour formatting (format: #[AA]RRGGBB)
    FG_DIMMED = "#8389a3"
    BG_FOCUSED = "#33374c"
    FG_FOCUSED = "#e8e9ec"
    # suffix for window labels when its length exceeds LABEL_SIZE
    OVERFLOW = ".."

    def _set_background_color(self, title, color):
        return f"%{{B{color}}}{title}%{{B-}}"

    def _set_foreground_color(self, title, color):
        return f"%{{F{color}}}{title}%{{F-}}"

    def _clamp_interpolated_title(self, title):
        """Returns a window title with a fixed length of LABEL_SIZE

        :param title: A window title
        :return: Title of fixed length
        """
        title = title.ljust(self.LABEL_SIZE, " ")
        if len(title) > self.LABEL_SIZE:
            cut_index = self.LABEL_SIZE - len(self.OVERFLOW)
            title = title[:cut_index] + self.OVERFLOW
        return f" {title} "

    def style_focused(self, title):
        """Returns a stylized window title for a focused node
        :param title: A window title
        """
        title = self._clamp_interpolated_title(title)
        title = self._set_background_color(title, self.BG_FOCUSED)
        title = self._set_foreground_color(title, self.FG_FOCUSED)
        return title

    def style_inactive(self, title):
        """Returns a stylized window title for an unfocused/inactive node
        :param title: A window title
        """
        title = self._clamp_interpolated_title(title)
        title = self._set_foreground_color(title, self.FG_DIMMED)
        return title


class WindowListInteractor(object):
    """Post-processing class for queried nodes and window information.

    :param repo: Repository of current state of nodes in reference desktop
    :param formatter: Formatter for generating the ouput for polybar module
    """

    def __init__(self, repo: WindowListRepo, formatter: WindowInfoFormatter):
        """Constructor method
        """
        self._repo = repo
        self._formatter = formatter

    def get_output(self):
        node_list = self._repo.get_window_list()
        node_focused = self._repo.get_focused_window()

        result = ""
        for n in node_list:
            title = n["title"]
            if n["id"] == node_focused["id"]:
                title = self._formatter.style_focused(title)
            else:
                title = self._formatter.style_inactive(title)
            result = result + title
        return result


class Controller(object):
    """A class to control communication with polybar.

    :param polybar_pid: The polybar process id to communicate window events to
    """
    CACHE_DIR = os.getenv("HOME") + "/.cache/polybar"
    HOOK_TAIL_ID = 1

    def __init__(self, polybar_pid=0, polybar_cache=None):
        """Constructor method
        """
        # default setup values
        self._polybar_pid = polybar_pid
        self._polybar_cache = polybar_cache
        if polybar_cache is None:
            self._polybar_cache = f"{self.CACHE_DIR}/window-list"

    def __del__(self):
        """Destructor method
        """
        self._handle_cleanup()

    def _destroy(self, sig: int = 0, frame=None):
        """Meant to be used with a signal trap. The traps are setup when the
        cache file is created. When an INT, QUIT, or TERM signal is received,
        this method is called.

        :param sig: signal number
        :param frame: a frame object
        :raises EOFError: termination condition for event loop
        """
        self._handle_cleanup()
        sys.exit(sig)
        # this point and beyond is reached only when signal is sent from a
        # thread that is not the main thread
        # i.e. this script is started in the background from another script
        if not sig == 0:
            raise EOFError

    def _handle_cleanup(self):
        """Helper for destructor and destroy signals while listening to events
        """
        if os.path.isfile(self._polybar_cache):
            os.remove(self._polybar_cache)

    def _redirect_output(self, output):
        """Helper for redirecting output based on state of Controller, or the
        passed args when starting this script.

        :effects: Writes to stdout or temporary file
        :param output: The formatted output to write
        """
        if self._polybar_pid == 0:
            # default behaviour
            print(output)
            return
        # non-zero pid; write to polybar cache and notify
        with open(self._polybar_cache, "w+") as f:
            print(output, file=f)
        self.polybar_hook_notify(self.HOOK_TAIL_ID)

    def _create_cache_dir(self):
        """Ensures parent directory for cache file exists
        :effects: Writes a local directory to Controller.CACHE_DIR
        """
        try:
            # ensure parent dir exists
            os.mkdir(self.CACHE_DIR, mode=0o755 | stat.S_IFDIR)
        except FileExistsError:
            pass

    def _create_cache_file(self):
        """Creates a unique cache file for the polybar module to read
        :effects: Writes a unique temporary local file specified by given args
        """
        try:
            os.mknod(self._polybar_cache, mode=0o644 | stat.S_IFREG)
        except FileExistsError:
            # clear contents
            f = os.open(self._polybar_cache, os.O_WRONLY | os.O_NONBLOCK)
            os.close(f)
        finally:
            # cleanup temp file on exit
            signals = [signal.SIGINT, signal.SIGQUIT, signal.SIGTERM]
            for sig in signals:
                if sig not in signal.valid_signals():
                    continue
                signal.signal(sig, self._destroy)

    @staticmethod
    def validate_polybar_pid(pid: int):
        """Validates existence of pid and determines if it belongs to polybar
        :param pid: The process id specified by given args
        """
        if pid < 0:
            raise ValueError
        try:
            os.kill(pid, 0)  # check process exists
        except (ProcessLookupError, PermissionError):
            pass
        else:
            # fetch process name of pid
            cmd = f"ps -p {pid} -o comm=".split()
            pipe = subprocess.run(cmd, capture_output=True, text=True)
            if pipe.stdout.rstrip() == "polybar":
                return True
        return False

    @property
    def cache_file(self) -> str:
        return self._polybar_cache

    @cache_file.setter
    def cache_file(self, cache_path: str):
        cache_parsed = pathlib.Path(cache_path)
        # format a unique name for temp file per polybar process
        self._polybar_cache = str(cache_parsed.parent) + \
            f"/{cache_parsed.name}.{self._polybar_pid}"

        self._create_cache_dir()
        self._create_cache_file()

    @property
    def polybar_pid(self) -> int:
        return self._polybar_pid

    @polybar_pid.setter
    def polybar_pid(self, pid: int):
        if self.validate_pid(pid):
            self._polybar_pid = pid

    @classmethod
    def tail(cls, polybar_pid: int, cache_path=None) -> str:
        if cache_path is None:
            cache_path = f"{cls.CACHE_DIR}/window-list"
        cache_path = str(pathlib.Path(cache_path)) + f".{polybar_pid}"
        with open(cache_path, "r") as rc:
            lines = rc.readlines()
            print(lines[-1] if len(lines) != 0 else "", end="")

    def polybar_hook_notify(self, hook_id: int):
        """Sends an inter-processing commuication message to a polybar module
        :param hook_id: a 1-based index refering to the tail hook id
        """
        hook = f"/tmp/polybar_mqueue.{self._polybar_pid}"
        # notify only if polybar ipc is enabled
        # see https://github.com/polybar/polybar/wiki/Module:-ipc for more info
        if not os.path.exists(hook):
            return
        try:
            if not stat.S_ISFIFO(os.stat(hook).st_mode):
                return
            with open(hook, "a") as f:
                print(f"hook:module/window-list{hook_id}", file=f)
        except FileNotFoundError:
            pass

    def start_listener(self):
        """Starts listening for bspwm events and reporting formatted output to
        a temporary cache file when polybar_pid is gt 0; otherwise, to stdout
        """
        # unique instance tied to polybar pid
        self.polybar_pid = self._polybar_pid
        if self._polybar_pid != 0:
            self.cache_file = self._polybar_cache

        d_node = NodeDriver()
        d_wminfo = WindowInfoDriver()
        repo = WindowListRepo(d_node, d_wminfo)
        formatter = WindowInfoFormatter()

        o = WindowListInteractor(repo, formatter)
        try:
            event = EventListener.start()
            while True:
                self._redirect_output(o.get_output())
                next(event)
        except (EOFError, KeyboardInterrupt):
            pass
        except Exception:
            # in case of unhandled exception, notify last time before exit
            self.polybar_hook_notify(self.HOOK_TAIL_ID)
            raise


def main(*args, **kwargs):
    parser = argparse.ArgumentParser()
    parser.add_argument("pid", type=int, nargs='?', default=0)
    parser.add_argument("cache", type=pathlib.Path, action="store", nargs='?')
    parser.add_argument(*["--start", "-s"], action="store_true")
    parser.add_argument(*["--tail", "-t"], action="store_true")
    setup_config = parser.parse_args(args)

    if setup_config.tail:
        try:
            Controller.tail(setup_config.pid, setup_config.cache)
        except FileNotFoundError as e:
            print(f"{e.strerror}: '{e.filename}'")
    if setup_config.start:
        c = Controller(setup_config.pid, setup_config.cache)
        c.start_listener()


if __name__ == "__main__":
    main(*sys.argv[1:])
    exit(0)
