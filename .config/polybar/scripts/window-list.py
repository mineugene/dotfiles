#!/usr/bin/env python

import argparse
import os
import pathlib
import re
import signal
import stat
import subprocess
import sys
import threading
import typing


class Node(object):
    """Represents a node with an attached window.
    :param kwargs: Dictionary of columns from wmctrl line
    """

    def __init__(self, **kwargs):
        """Constructor method
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
        "node_transfer",
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
    QUERIES = {
        "focused": "bspc query -N -n focused.window".split(),
        "local": "bspc query -N -n .local.window".split(),
        "same_class": "bspc query -N -n .local.same_class".split(),
        "flags": "bspc wm --get-status".split(),
    }

    def _safe_hex_to_dec(self, node_id: str) -> int:
        """A query output is typically in hex (0x..) format; therefore,
        it is mapped into int for ease of comparison

        :param node_id: The id number of node in base-16
        :return: Node id in base-10
        """
        id = 0
        try:
            id = int(node_id, 16)
        except ValueError:
            pass
        return id

    def _select(self, query_id: str) -> typing.Iterable[int]:
        """A general querying method that returns a formatted list from the
        resulting raw output

        :param query_id: An id from this class' QUERIES dictionary
        :return: List of node id
        """
        cmd = self.QUERIES.get(query_id)
        pipe = subprocess.run(cmd, capture_output=True, text=True)
        return pipe.stdout.rstrip().split("\n")

    def _id_map(self, output: list) -> typing.Iterable[int]:
        """Maps the given lines of node id from a query into a list of integers

        :param output: Lines from query output
        :return: List of node id
        """
        return list(
            filter(lambda n: n != 0, map(self._safe_hex_to_dec, output))
        )

    def _report_map(self, status: str) -> dict:
        """Maps the report line from probing the overall status

        :param output: Full line from status report
        :return: Hashed montior id and its state
        """
        result = {}
        if status == "":
            return result

        report = re.split(r"[W:][Mm]", status)[1:]
        for rep in report:
            monitor, *state = rep.split(":")
            result[monitor] = state
        return result

    def query_focused(self) -> typing.Iterable[int]:
        """Queries the currently focused node id in base-10
        :return: Focused node id
        """
        node_focused_id = self._id_map(self._select("focused"))
        return node_focused_id

    def query_local_windows(self) -> typing.Iterable[int]:
        """Queries a list of nodes in the reference desktop that contain an
        attached window
        :return: List of node id in reference desktop
        """
        node_win_id = self._id_map(self._select("local"))
        return node_win_id

    def query_local_class(self) -> typing.Iterable[int]:
        """Queries a list of nodes with the same window class
        :return: List of node id with the same class as the reference window
        """
        node_cls_id = self._id_map(self._select("same_class"))
        return node_cls_id

    def report(self) -> dict:
        """Returns a report of the current state of all monitors
        :return: Hashed monitor id and its state
        """
        report = self._report_map(self._select("flags"))
        return report


class WindowInfoDriver(object):
    """Retrieves window information for all windows using 'wmctrl'.
    """

    def _map_wmctrl_line(self, line: str) -> dict:
        """Maps lines from 'wmctrl' into a dictionary of each column:

        col header
        --- ------
        0   window id
        1   desktop id
        2   pid
        3-6 geometry (x-offset, y-offset, width, height)
        7   class name
        8   hostname
        9   window title

        :param line: A line from 'wmctrl' list output
        :return: Hashed column names with its values
        """
        # filter out redundant whitespace special characters
        wminfo = " ".join(
            line.encode("ascii", errors="ignore").decode().split()
        )
        # parse columns
        wminfo = wminfo.split(" ", 9)
        wminfo_hash = {
            "id": int(wminfo[0], 0),
            "desktop": int(wminfo[1]),
            "pid": int(wminfo[2]),
            "geometry": tuple(map(int, wminfo[3:7])),
            "class": wminfo[7].split(".")[-1].lower(),
        }
        try:
            wminfo_hash.update(title=wminfo[9])
        except IndexError:
            wminfo_hash.update(title=wminfo_hash["class"])
        finally:
            return wminfo_hash

    def get_info_map(self) -> dict:
        """Retrieves info of all windows in every desktop
        :return: Hashed window ids with its property values
        """
        cmd = "wmctrl -pGxl".split()
        pipe = subprocess.run(cmd, capture_output=True, text=True)
        out = pipe.stdout.rstrip().split("\n")

        result = {}
        for line in filter(lambda n: n != "", out):
            tokenized_line = self._map_wmctrl_line(line)
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

    def _map_to_domain(
        self,
        node_id: list,
        wminfo_hash: dict,
    ) -> typing.Iterator[dict]:
        for id in node_id:
            if id not in wminfo_hash:
                continue
            node = Node(id=id, **wminfo_hash[id])
            yield node.attrs

    def _filter(self, hash_map: dict, filter: list) -> list:
        result = []
        if filter is not None:
            result = [hash_map.pop(id, None) for id in filter]
        return result

    def _group(self, winlist: typing.Iterable[dict], group="class") -> list:
        return sorted(winlist, key=lambda i: i.get(group, ""))

    def get_focused_window(self) -> dict:
        """Gets the window properties of the currently focused window. The dict
        keys match the description from :class:`Node`

        :return: Window properties of the focused node
        """
        node_focused = self._d_node.query_focused()
        wminfo_hash = self._d_wminfo.get_info_map()

        result = list(self._map_to_domain(node_focused, wminfo_hash))
        if len(result) == 0:
            return {}
        return result.pop()

    def get_same_class_windows(self, filter=None) -> list:
        """Gets a list of windows and its properties that are in the same class
        as the reference window. They match the description from :class:`Node`

        :return: List of nodes of the same class, and their window properties
        """
        node_cls_id = self._d_node.query_local_class()
        wminfo_hash = self._d_wminfo.get_info_map()

        self._filter(wminfo_hash, filter)
        result = list(self._map_to_domain(node_cls_id, wminfo_hash))
        return result

    def get_window_list(self, filter=None) -> list:
        """Gets a list of windows and its properties, matching the description
        from :class:`Node`

        :param filter: nodes to filter out from final result
        :return: List of nodes and their window properties
        """
        node_win_id = self._d_node.query_local_windows()
        wminfo_hash = self._d_wminfo.get_info_map()

        self._filter(wminfo_hash, filter)
        result = self._group(self._map_to_domain(node_win_id, wminfo_hash))
        return result


class WindowInfoFormatter(object):
    """Window title formatter by string interpolation for polybar module.
    """
    # window label size
    LABEL_SIZE = 17  # must be greater than or equal to len(OVERFLOW)+1
    LABEL_SIZE_FOCUSED = 27
    # colour formatting (format: #[AA]RRGGBB)
    FG_DIMMED = "#6b7089"
    BG_FOCUSED = "#1e2132"
    FG_FOCUSED = "#c6c8d1"
    FG_FOCUSED_CLS = "#6b7089"
    BG_SAME_CLASS = "#5b7881"
    FG_SAME_CLASS = "#d2d4de"
    # suffix for window labels when its length exceeds LABEL_SIZE
    OVERFLOW = ".."
    # separator between class name and window title for the focused label
    DELIM_FOCUSED = " - "
    # surrounding character for window titles
    # if paren, bracket, brace, then must be open type
    SURROUND_CHAR = "["
    # left-right padding for window title
    PADDING = 1

    def _set_bg_color(self, title: str, color: str) -> str:
        return f"%{{B{color}}}{title}%{{B-}}"

    def _set_fg_color(self, title: str, color: str) -> str:
        return f"%{{F{color}}}{title}%{{F-}}"

    def _set_surround(self, title: str) -> str:
        open = self.SURROUND_CHAR
        close = {
            "[": "]",
            "{": "}",
            "(": ")",
        }.get(self.SURROUND_CHAR, self.SURROUND_CHAR)
        return open + title + close

    def _set_padding(self, title: str) -> str:
        pad = " " * self.PADDING
        return pad + title + pad

    def _clamp_title(self, title: str, limit: int) -> str:
        """Returns a window title with a fixed length of LABEL_SIZE

        :param title: A window title
        :return: Title of fixed length
        """
        title = title.ljust(limit, " ")
        if len(title) > limit:
            cut_index = limit - len(self.OVERFLOW)
            title = title[:cut_index] + self.OVERFLOW
        return title

    def _strip_focused_delim(
        self, pattern: typing.Pattern[str], label: str
    ) -> str:
        """Strip out the left substring of title that matches the given pattern
        :param pattern: Substring to strip from title
        :param title: A focused window label
        """
        cls, name = label.split(self.DELIM_FOCUSED, 1)
        name = re.sub(pattern, "", name)
        return cls + self.DELIM_FOCUSED + name

    def style_focused(self, title: str) -> str:
        """Returns a stylized window title for a focused node
        :param title: A window title
        """
        label = self._strip_focused_delim(r"^[^\w]*?- +", title)
        label = self._clamp_title(label, self.LABEL_SIZE_FOCUSED)

        cls = name = ""
        try:
            cls, name = label.split(self.DELIM_FOCUSED, 1)
        except ValueError:
            cls = "UNKNOWN"
            name = "".ljust(
                self.LABEL_SIZE_FOCUSED - len(self.DELIM_FOCUSED) - len(cls)
            )
        label = self._set_fg_color(
            cls + self.DELIM_FOCUSED, self.FG_FOCUSED_CLS
        ) + self._set_fg_color(self._set_surround(name), self.FG_FOCUSED)
        label = self._set_padding(label)
        label = self._set_bg_color(label, self.BG_FOCUSED)
        return label

    def style_inactive(self, title: str) -> str:
        """Returns a stylized window title for an unfocused/inactive node
        :param title: A window title
        """
        title = self._set_surround(self._clamp_title(title, self.LABEL_SIZE))
        title = self._set_padding(title)
        title = self._set_fg_color(title, self.FG_DIMMED)
        return title

    def style_same_class(self, title: str) -> str:
        """Returns a stylized window title for a node with the same class as
        the focused node
        :param title: A window title
        """
        title = self._set_surround(self._clamp_title(title, self.LABEL_SIZE))
        title = self._set_padding(title)
        title = self._set_bg_color(title, self.BG_SAME_CLASS)
        title = self._set_fg_color(title, self.FG_SAME_CLASS)
        return title


class WindowListInteractor(object):
    """Post-processing class for queried nodes and window information. Produces
    the final output line that the polybar module is to receive.

    :param repo: Repository of current state of nodes in reference desktop
    :param formatter: Formatter for generating the ouput for polybar module
    """

    def __init__(self, repo: WindowListRepo, formatter: WindowInfoFormatter):
        """Constructor method
        """
        self._repo = repo
        self._formatter = formatter

    def get_output(self):
        node_focused = self._repo.get_focused_window()
        node_focused_id = node_focused.get("id", None)
        filter = [node_focused_id] if node_focused_id else []

        node_cls_list = self._repo.get_same_class_windows(filter)
        if node_focused_id:
            filter += map(lambda n: n.get("id", 0), node_cls_list)

        node_list = self._repo.get_window_list(filter)

        result = ""
        if node_focused_id:
            title = node_focused["class"] + " - " + node_focused["title"]
            result += self._formatter.style_focused(title)
        for n in node_cls_list:
            result += self._formatter.style_same_class(n["title"])
        for n in node_list:
            result += self._formatter.style_inactive(n["title"])
        return result


class ThreadedRefresh(threading.Thread):
    """A thread to be started while waiting for the next input/event.
    Runs the given target at equal intervals until thread is stopped.
    The returned object may be printed to stdout, or redirected with a
    custom printer.

    :effects: Writes to stdout, or redirected output through custom printer
    :param interval: Time in miliseconds between calls to target
    :param target: Function to invoke
    :param start_delay: Delay before the first invocation of target
    :param timeout: Time in miliseconds for thread to expire
    :param printer: Writer for return object of target
    """

    def __init__(
        self,
        interval: int,
        target,
        *,
        start_delay=1000,
        timeout=6e5,
        printer=print
    ):
        super().__init__(target=target)

        self.interval = interval
        self.start_delay = start_delay
        self.timeout = timeout
        self.printer = printer

        self._target = target
        self._terminate = threading.Event()

    def run(self):
        """Method representing the thread's activity.
        Invokes the callable object passed to the object's constructor as the
        target argument.
        """
        try:
            iter_count = 0
            self._terminate.wait(self.start_delay / 1000)
            while not self.stopped:
                self.printer(self._target())
                self._terminate.wait(self.interval / 1000)
                if self.interval * iter_count > self.timeout:
                    self.stop()
                iter_count += 1
        finally:
            del self._target

    def stop(self):
        """Sets flag to terminate all activity. Waits on printer and target to
        finish before termination.
        """
        self._terminate.set()

    @property
    def stopped(self) -> bool:
        return self._terminate.is_set()


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
        if self.validate_polybar_pid(pid):
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
        t: ThreadedRefresh = None
        try:
            event = EventListener.start()
            while True:
                self._redirect_output(o.get_output())
                t = ThreadedRefresh(
                    500, o.get_output, printer=self._redirect_output
                )
                t.start()
                next(event)
                t.stop()
        except (EOFError, KeyboardInterrupt):
            pass
        except Exception:
            # in case of unhandled exception, notify last time before exit
            self.polybar_hook_notify(self.HOOK_TAIL_ID)
            raise
        finally:
            # stop remaining threads
            if hasattr(t, "stop"):
                t.stop()


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
