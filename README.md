# 🪟 orcsome3

Python 3 scripting for a **NETWM-compliant X11 window manager you already run** (Openbox, etc.). It is not a window manager.

Based in [orcsome](https://github.com/baverman/orcsome). Linux / X11 only. Requires **Python 3.8 or newer** (3.8, 3.9, 3.10, … current).

You write `~/.config/orcsome3/config.py`. orcsome3 grabs keys, watches window create/destroy/property/focus, can change EWMH state and icons, and can post desktop notifications over D-Bus.

## 🏗️ Architecture

```text
config.py  (your script)
  └─ orcsome3          WindowManager, Window, Notification, get_wm, keys
       └─ orcsome3.libs.xlib / ev     typed Python wrappers
            └─ orcsome3_backend.so    Cython (Xlib + statically linked ev / cairo / Magick / gd / resvg)
                 └─ libX11, libXext, libXss, libXtst   (system, dynamic)
```

- **Public API** lives in `orcsome3/` (`get_wm`, `window_manager`, `notify`, `keys`). That is what `config.py` should import.
- **Only** `orcsome3.libs.xlib` and `orcsome3.libs.ev` import `orcsome3_backend`. Do not import the `.so` from `config.py`.
- The backend is typed via a generated `orcsome3_backend.pyi` (`make stubs`). The package ships `py.typed`.
- libev, Cairo, ImageMagick 7, gd, resvg (and their image-format deps) are **downloaded and statically linked** into the `.so`. You do **not** install ImageMagick from source yourself. X11 stays a normal system library.

## ✨ What you can do

- Global and per-window hotkeys (`XGrabKey`), including CapsLock/NumLock variants
- React to window create / manage / destroy / property / focus
- NETWM/EWMH: desktops, maximize, fullscreen, decorations, close, move/resize, icons
- Freedesktop notifications (`dbus-next` → `org.freedesktop.Notifications`)
- Typed `config.py` (mypy / basedpyright)

## 📦 Install

### X11 libraries

orcsome3 needs the usual X11 client libraries (`libX11`, `libXext`, `libXss`, `libXtst`). A Linux desktop almost always has them already. Install them only if the module fails to load:

```bash
# Debian / Ubuntu
sudo apt install libx11-6 libxss1 libxext6 libxtst6

# Arch
sudo pacman -S libx11 libxss libxext libxtst
```

Python deps (`dbus-next`, `typing_extensions`) come with the package.

### From PyPI

```bash
python3 -m pip install orcsome3
```

Linux manylinux wheels cover CPython **3.8 through current** (3.15 as of cibuildwheel 4.2). No musllinux, free-threaded (`3.14t`, …), Windows, or macOS. A GitHub Release (or **Upload Python Package** from Actions) publishes the sdist and wheels. Bump the `pypa/cibuildwheel` pins in `.github/workflows/python-publish.yml` when a new CPython ships.

### Build from source

First-time native build fetches git/tarball sources and compiles static libs. You need a C/C++ toolchain, the X11 **headers**, and:

```bash
# Debian / Ubuntu
sudo apt install git cmake autoconf automake libtool pkg-config meson ninja-build \
  libx11-dev libxss-dev libxext-dev libxtst-dev curl
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y   # resvg

# Arch
sudo pacman -S git cmake autoconf automake libtool pkgconf meson ninja \
  libx11 libxss libxext libxtst rust
```

Then:

```bash
git clone https://github.com/ahsand97/orcsome3.git
cd orcsome3
make native          # static libs + orcsome3_backend.so  (slow once)
python3 -m pip install .
```

`pip install .` **reuses** `orcsome3_built_libraries/`; it does not download those libs again. Run `make native` first on a clean clone.

To hack without installing the package:

```bash
make dev             # venv + deps + native
make run             # python -m orcsome3  (needs ~/.config/orcsome3/config.py)
```

## 🚀 Quick start

Create `~/.config/orcsome3/config.py` (or pass `-c`). If the file is missing, orcsome3 logs an error and exits.

Most hooks take `window=None` (every window) or `window=wm.event_window` (one id, usually nested under `on_manage`). Callbacks that take no event use `wm.event_window`. Decorated functions get `.remove()` to unregister.

### Decorators

- **`@wm.on_init` / `@wm.on_deinit`** — no parentheses. `on_init` runs once at startup after root events are selected, before existing clients are scanned. `on_deinit` runs in `stop()` after key/button grabs and timers are torn down.
- **`@wm.on_key(...)`** — `XGrabKey` on KeyPress. Default is a **global** hotkey (grab on the root). The callback’s `window` is that grab window; use `wm.current_window` for the focused client. Pass `window_matcher=` to grab on matching clients instead. orcsome3 consumes the key unless `propagate_event=True`. CapsLock/NumLock variants are grabbed for you. `"Control + b"` or a `KeyDefinition`; modifiers `Control`/`Ctrl`, `Alt`/`Meta`, `Shift`, `Win`/`Super`, `AnyModifier`; keys are X keysym names (`XK_` stripped).
- **`@wm.on_key_release(...)`** — same grab as `on_key`, but KeyRelease. Register both for the same combo; they share one `XGrabKey`.
- **`@wm.on_button(...)`** — `XGrabButton` on ButtonPress (`BUTTONS.Button1`…`Button5` or `AnyButton`). Same root-vs-`window_matcher` and `propagate_event` rules as `on_key`.
- **`@wm.on_create(...)`** — CreateNotify, **including** windows already mapped when orcsome3 starts. Optional `matcher=WindowMatchers(...)`. Use `event_window` in the callback.
- **`@wm.on_manage(...)`** — same as `on_create`, but **skips** the startup sweep. Nest per-window `@wm.on_destroy(window=...)` (and similar) here so you do not attach once per existing client.
- **`@wm.on_destroy(...)`** — DestroyNotify. After destroy, reading properties on that id will fail.
- **`@wm.on_property_change(property="...")`** — PropertyNotify when an atom (`_NET_WM_STATE`, …) gets a new value.
- **`@wm.on_focus()` / `@wm.on_unfocus()`** — FocusIn / FocusOut (`NotifyNormal` / `NotifyWhileGrabbed` only; pointer-detail and grab-notify are ignored).
- **`@wm.on_map()` / `@wm.on_unmap()` / `@wm.on_configure()`** — MapNotify / UnmapNotify / ConfigureNotify. Callback is `(window, event)`. Configure fires often during resize; size is `event.width` / `event.height` (not a later `get_geometry()`).
- **`@wm.on_client_message(message_type="...")`** — ClientMessage filtered by atom name (`_NET_ACTIVE_WINDOW`, …). Callback is `(window, event)`.
- **`@wm.on_timer(timeout=...)`** — repeating libev timer (seconds). Return `True` to stop; `None`/falsy keeps it. Also `.start()` / `.stop()` / `.again()`. Needs the process event loop (normal `orcsome3` has one).

Example `config.py`:

```python
from pathlib import Path
from typing import Optional

from orcsome3 import get_wm
from orcsome3.keys import KeyboardModifiers, KeyDefinition, WindowMatchers
from orcsome3.libs.xlib import (
    BUTTONS,
    XButtonEvent,
    XClientMessageEvent,
    XConfigureEvent,
    XKeyEvent,
    XMapEvent,
    XUnmapEvent,
)
from orcsome3.notify import Notification
from orcsome3.window_manager import Window, WindowManager

wm: WindowManager = get_wm()


@wm.on_init
def on_start() -> None:
    print("orcsome3 started")


@wm.on_deinit
def on_stop() -> None:
    print("orcsome3 stopping")


# Global hotkey. `window` is root; focused client is `wm.current_window`.
@wm.on_key(key_definition="Control + b")
def on_control_b(window: Window, event: XKeyEvent) -> None:
    print("Control + b")


# Per-client grab (every URxvt, including ones already mapped after init).
@wm.on_key(
    key_definition=KeyDefinition(modifiers=KeyboardModifiers.Control, key=KeyDefinition.Key(name="d")),
    window_matcher=WindowMatchers(class_="URxvt"),
)
def close_urxvt(window: Window, event: XKeyEvent) -> None:
    window.close()


@wm.on_key_release(key_definition="Control + b")
def on_control_b_up(window: Window, event: XKeyEvent) -> None:
    print("Control + b released")


@wm.on_button(button=BUTTONS.Button1, modifiers=KeyboardModifiers.Control)
def on_ctrl_click(window: Window, event: XButtonEvent) -> None:
    print(event.x, event.y)


@wm.on_create()
def on_any_create() -> None:
    print(wm.event_window.get_name_and_class())


@wm.on_manage(matcher=WindowMatchers(name="easyeffects", class_="easyeffects"))
def on_easyeffects() -> None:
    wm.event_window.set_icon(icon=Path("/path/to/icon.svg"))

    @wm.on_destroy(window=wm.event_window)
    def on_easyeffects_gone() -> None:
        print("easyeffects closed")


@wm.on_destroy()
def on_any_destroy() -> None:
    print(f"destroyed {wm.event_window}")


@wm.on_property_change(property="_NET_WM_STATE")
def hide_title_bar_when_maximized() -> None:
    w: Window = wm.event_window
    if w.maximized_horz and w.maximized_vert:
        if w.decorated:
            w.set_state(decorate=False)
    elif not w.decorated:
        w.set_state(decorate=True)


@wm.on_focus()
def on_focus() -> None:
    print(f"focus {wm.event_window}")


@wm.on_unfocus()
def on_unfocus() -> None:
    print(f"unfocus {wm.event_window}")


@wm.on_map()
def on_map(window: Window, event: XMapEvent) -> None:
    print(f"mapped {window}")


@wm.on_unmap()
def on_unmap(window: Window, event: XUnmapEvent) -> None:
    print(f"unmapped {window}")


@wm.on_configure()
def on_configure(window: Window, event: XConfigureEvent) -> None:
    print(window, event.width, event.height)


@wm.on_client_message(message_type="_NET_ACTIVE_WINDOW")
def on_active(window: Window, event: XClientMessageEvent) -> None:
    print(window, event.message_type)


@wm.on_timer(timeout=60.0)
def every_minute() -> Optional[bool]:
    print("tick")
    return None  # return True to stop


@wm.on_manage(matcher=WindowMatchers(name="Navigator", class_="firefox", window_type=["_NET_WM_WINDOW_TYPE_NORMAL"]))
def firefox_opened() -> None:
    n: Notification = Notification(
        app_name="Firefox",
        summary="Firefox is now open!",
        body="<b>Notification body</b>",
        actions=[Notification.Action(visible_name="Action #1", callback=lambda: print("Action #1"))],
        on_close=lambda: print("notification closed"),
        hints=Notification.Hints(urgency=Notification.Hints.Urgency.NORMAL),
    )
    n.show()
```

Then:

```bash
orcsome3
# or: python3 -m orcsome3
```

Useful flags: `--config PATH`, `--log-file PATH`, `--log-level DEBUG`, `--version`.

One process per `$DISPLAY` (lock under `$XDG_RUNTIME_DIR/orcsome3/`). Extra monitors on the same X server share that instance. A second X server (Chrome Remote Desktop, VNC, `:1`) is a separate process and does not steal grabs from `:0`. Saving the loaded config reloads it (or send `SIGUSR1`). `SIGINT` / `SIGTERM` quit.

A tray icon appears when your panel has a StatusNotifier (SNI) host — most do (KDE, many tint2/Waybar/Polybar setups, etc.). The menu is **Reload config** and **Quit**. If no host is on the session bus, there is no icon; signals still work.

## 🛠️ Develop

| Command | What it does |
| --- | --- |
| `make native` | Download/build static libs and compile the Cython backend |
| `make native-fast` | Re-cythonize/link only (needs a prior `native`) |
| `make native-rebuild` | Wipe the lib cache and rebuild |
| `make stubs` | Regenerate `orcsome3_backend.pyi` from the `.pyx` (needs the `.so`) |
| `make format` / `make lint` | ruff, mypy, basedpyright, extra checks, stub `--check` |
| `make test` | `unittest` in `tests/` (X tests skip if the display cannot be opened; grab delivery prefers Xephyr/Xvfb) |
| `make clean` | Build artifacts, `orcsome3_built_libraries/`, `.so` |

Do not hand-edit generated `.c` files or `orcsome3_built_libraries/`.

`python -m orcsome3.libs.build --build-dir .` is the same as `make native`. `--dynamic` links system libev/gd/Magick instead of the static copies.

## 📄 License

MIT. See [LICENSE](LICENSE).
