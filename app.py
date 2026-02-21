import ctypes
import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, Button, Frame, Label, Listbox, Tk
from ctypes import wintypes

import keyboard
import vgamepad as vg
from pynput import mouse


# Windows API setup
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_MOUSE_LL = 14
WM_MOUSEWHEEL = 0x020A
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
HC_ACTION = 0

MOUSE_EVENTS_TO_BLOCK = {
    WM_MOUSEWHEEL,
    WM_MBUTTONDOWN,
    WM_MBUTTONUP,
    WM_RBUTTONDOWN,
    WM_RBUTTONUP,
    WM_LBUTTONDOWN,
    WM_LBUTTONUP,
    WM_XBUTTONDOWN,
    WM_XBUTTONUP,
}

MOUSE_DOWN_TO_NAME = {
    WM_LBUTTONDOWN: "mouse_left",
    WM_RBUTTONDOWN: "mouse_right",
    WM_MBUTTONDOWN: "mouse_middle",
}

MOUSE_UP_TO_NAME = {
    WM_LBUTTONUP: "mouse_left",
    WM_RBUTTONUP: "mouse_right",
    WM_MBUTTONUP: "mouse_middle",
}


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", ctypes.c_ulong),
        ("flags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


LowLevelMouseProc = ctypes.WINFUNCTYPE(
    ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)


@dataclass
class MappingTarget:
    name: str
    button: int


class MouseKeyboardToGamepad:
    CONFIG_FILE = Path("mapping.json")

    def __init__(self) -> None:
        self.gamepad = vg.VX360Gamepad()
        self.gamepad_mode = False
        self.running = True
        self.mouse_dx = 0.0
        self.mouse_dy = 0.0
        self.mouse_lock_center = (960, 540)

        self.mapping_targets = [
            MappingTarget("A", vg.XUSB_BUTTON.XUSB_GAMEPAD_A),
            MappingTarget("B", vg.XUSB_BUTTON.XUSB_GAMEPAD_B),
            MappingTarget("X", vg.XUSB_BUTTON.XUSB_GAMEPAD_X),
            MappingTarget("Y", vg.XUSB_BUTTON.XUSB_GAMEPAD_Y),
            MappingTarget("LB", vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER),
            MappingTarget("RB", vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER),
            MappingTarget("Back", vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK),
            MappingTarget("Start", vg.XUSB_BUTTON.XUSB_GAMEPAD_START),
            MappingTarget("LThumb", vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB),
            MappingTarget("RThumb", vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB),
        ]

        self.mapping = self._load_mapping()
        self.capture_target = None

        self._mouse_hook_ptr = LowLevelMouseProc(self._low_level_mouse_proc)
        self._mouse_hook = None

        self._install_hooks()
        self._start_mouse_listener()

    def _load_mapping(self):
        default = {
            "A": "space",
            "B": "shift",
            "X": "q",
            "Y": "e",
            "LB": "mouse_left",
            "RB": "mouse_right",
            "Back": "tab",
            "Start": "enter",
            "LThumb": "ctrl",
            "RThumb": "mouse_middle",
        }
        if self.CONFIG_FILE.exists():
            return {**default, **json.loads(self.CONFIG_FILE.read_text())}
        return default

    def _save_mapping(self):
        self.CONFIG_FILE.write_text(json.dumps(self.mapping, indent=2))

    def _start_mouse_listener(self):
        self.last_mouse_position = None

        def on_move(x, y):
            if not self.gamepad_mode:
                self.last_mouse_position = (x, y)
                return
            if self.last_mouse_position is None:
                self.last_mouse_position = (x, y)
                return
            dx = x - self.last_mouse_position[0]
            dy = y - self.last_mouse_position[1]
            self.mouse_dx += dx
            self.mouse_dy += dy
            self.last_mouse_position = (x, y)
            user32.SetCursorPos(*self.mouse_lock_center)
            self.last_mouse_position = self.mouse_lock_center

        self.mouse_listener = mouse.Listener(on_move=on_move)
        self.mouse_listener.start()

    def _install_hooks(self):
        self._mouse_hook = user32.SetWindowsHookExA(
            WH_MOUSE_LL,
            self._mouse_hook_ptr,
            kernel32.GetModuleHandleW(None),
            0,
        )

        keyboard.on_press(self._on_key_down)
        keyboard.on_release(self._on_key_up)

    def _low_level_mouse_proc(self, n_code, w_param, l_param):
        if n_code == HC_ACTION:
            if self.capture_target is not None and w_param in MOUSE_DOWN_TO_NAME:
                self.mapping[self.capture_target] = MOUSE_DOWN_TO_NAME[w_param]
                self.capture_target = None
                self._save_mapping()
                self.refresh_mapping_list()
                self.status_label.config(text="Mapping captured")
                return 1

            if w_param in MOUSE_DOWN_TO_NAME:
                self._apply_mapping_press(MOUSE_DOWN_TO_NAME[w_param])
            elif w_param in MOUSE_UP_TO_NAME:
                self._apply_mapping_release(MOUSE_UP_TO_NAME[w_param])

            if self.gamepad_mode and w_param in MOUSE_EVENTS_TO_BLOCK:
                return 1

        return user32.CallNextHookEx(self._mouse_hook, n_code, w_param, l_param)

    def _key_to_target(self, key_name):
        for target in self.mapping_targets:
            if self.mapping[target.name] == key_name:
                return target
        return None

    def _apply_mapping_press(self, source_name):
        target = self._key_to_target(source_name)
        if target is None:
            return
        self.gamepad.press_button(button=target.button)
        self.gamepad.update()

    def _apply_mapping_release(self, source_name):
        target = self._key_to_target(source_name)
        if target is None:
            return
        self.gamepad.release_button(button=target.button)
        self.gamepad.update()

    def _on_key_down(self, event):
        name = event.name
        if name == "f1":
            self.toggle_mode()
            return

        if self.capture_target is not None:
            self.mapping[self.capture_target] = name
            self.capture_target = None
            self._save_mapping()
            self.refresh_mapping_list()
            return

        self._apply_mapping_press(name)

    def _on_key_up(self, event):
        self._apply_mapping_release(event.name)

    def _left_stick_from_wasd(self):
        x = 0
        y = 0
        if keyboard.is_pressed("a"):
            x -= 1
        if keyboard.is_pressed("d"):
            x += 1
        if keyboard.is_pressed("w"):
            y += 1
        if keyboard.is_pressed("s"):
            y -= 1
        return x, y

    def _clamp_stick(self, value):
        return max(-32768, min(32767, int(value)))

    def _update_loop(self):
        sensitivity = 2200
        while self.running:
            lx, ly = self._left_stick_from_wasd()
            self.gamepad.left_joystick(
                x_value=self._clamp_stick(lx * 32767),
                y_value=self._clamp_stick(ly * 32767),
            )

            rx = self._clamp_stick(self.mouse_dx * sensitivity)
            ry = self._clamp_stick(-self.mouse_dy * sensitivity)
            self.gamepad.right_joystick(x_value=rx, y_value=ry)

            self.mouse_dx *= 0.45
            self.mouse_dy *= 0.45

            self.gamepad.update()
            time.sleep(0.005)

    def _set_cursor_visibility(self, visible: bool):
        user32.ShowCursor(visible)

    def toggle_mode(self):
        self.gamepad_mode = not self.gamepad_mode
        if self.gamepad_mode:
            self._set_cursor_visibility(False)
            user32.SetCursorPos(*self.mouse_lock_center)
            self.last_mouse_position = self.mouse_lock_center
            self.status_label.config(text="Gamepad mode ON (F1 to disable)")
        else:
            self._set_cursor_visibility(True)
            self.status_label.config(text="Normal mode ON (F1 to enable)")

    def _capture_mapping(self):
        selection = self.mapping_list.curselection()
        if not selection:
            return
        selected_name = self.mapping_targets[selection[0]].name
        self.capture_target = selected_name
        self.status_label.config(text=f"Press a key/mouse binding for {selected_name}")

    def refresh_mapping_list(self):
        self.mapping_list.delete(0, END)
        for target in self.mapping_targets:
            self.mapping_list.insert(END, f"{target.name:<8} -> {self.mapping[target.name]}")

    def build_ui(self):
        root = Tk()
        root.title("Mouse + Keyboard to Virtual Gamepad")
        root.geometry("520x360")

        top = Frame(root)
        top.pack(fill=BOTH, padx=10, pady=10)

        Label(top, text="Mappings (select one and click Remap)").pack()

        self.mapping_list = Listbox(top, height=14)
        self.mapping_list.pack(fill=BOTH, expand=True)
        self.refresh_mapping_list()

        actions = Frame(root)
        actions.pack(fill=BOTH, padx=10, pady=10)

        Button(actions, text="Remap selected", command=self._capture_mapping).pack(side=LEFT)
        Button(actions, text="Save", command=self._save_mapping).pack(side=LEFT)
        Button(actions, text="Toggle mode (F1)", command=self.toggle_mode).pack(side=RIGHT)

        self.status_label = Label(root, text="Normal mode ON (F1 to enable)")
        self.status_label.pack(padx=10, pady=10)

        def on_close():
            self.running = False
            if self._mouse_hook:
                user32.UnhookWindowsHookEx(self._mouse_hook)
            self.mouse_listener.stop()
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_close)

        threading.Thread(target=self._update_loop, daemon=True).start()
        root.mainloop()


if __name__ == "__main__":
    app = MouseKeyboardToGamepad()
    app.build_ui()
