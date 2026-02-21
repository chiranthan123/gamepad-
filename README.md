# Mouse/Keyboard to Virtual Gamepad Bridge

This project provides a Windows desktop utility that:

- Converts mouse movement into **right joystick** movement.
- Uses **WASD** to control the **left joystick**.
- Lets you remap keyboard/mouse inputs to gamepad buttons from a GUI.
- Toggles between normal mode and gamepad mode with **F1**.

## Behavior in gamepad mode

When gamepad mode is ON:

- Cursor is hidden.
- Cursor is locked to the center and movement is used as right-stick input.
- Mouse click, middle-button, and wheel messages are blocked system-wide.

When gamepad mode is OFF:

- Normal keyboard/mouse behavior resumes.

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

## Default mappings

- A -> `space`
- B -> `shift`
- X -> `q`
- Y -> `e`
- LB -> `mouse_left`
- RB -> `mouse_right`
- Back -> `tab`
- Start -> `enter`
- LThumb -> `ctrl`
- RThumb -> `mouse_middle`

Mappings are saved to `mapping.json`.
