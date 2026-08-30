# 🪟 orcsome3

Python 3 scripting for a **NETWM-compliant X11 window manager you already run** (Openbox, etc.). It is not a window manager.

Based in [orcsome](https://github.com/baverman/orcsome). Linux / X11 only. Requires **Python 3.8 or newer** (3.8, 3.9, 3.10, … current).

You write `~/.config/orcsome3/rc.py`. orcsome3 grabs keys, watches window create/destroy/property/focus, can change EWMH state and icons, and can post desktop notifications over D-Bus.

## 🏗️ Architecture

```text
rc.py  (your script)
  └─ orcsome3          WindowManager, Window, Notification, get_wm, keys
       └─ orcsome3.libs.xlib / ev     typed Python wrappers
            └─ orcsome3_backend.so    Cython (Xlib + statically linked ev / cairo / Magick / gd / resvg)
                 └─ libX11, libXext, libXss   (system, dynamic)
```

- **Public API** lives in `orcsome3/` (`get_wm`, `window_manager`, `notify`, `keys`). That is what `rc.py` should import.
- **Only** `orcsome3.libs.xlib` and `orcsome3.libs.ev` import `orcsome3_backend`. Do not import the `.so` from `rc.py`.
- The backend is typed via a generated `orcsome3_backend.pyi` (`make stubs`). The package ships `py.typed`.
- libev, Cairo, ImageMagick 7, gd, resvg (and their image-format deps) are **downloaded and statically linked** into the `.so`. You do **not** install ImageMagick from source yourself. X11 stays a normal system library.

## ✨ What you can do

- Global and per-window hotkeys (`XGrabKey`), including CapsLock/NumLock variants
- React to window create / manage / destroy / property / focus
- NETWM/EWMH: desktops, maximize, fullscreen, decorations, close, move/resize, icons
- Freedesktop notifications (`dbus-next` → `org.freedesktop.Notifications`)
- Typed `rc.py` (mypy / basedpyright)

## 📦 Install

### Runtime (always)

An X session and the X11 client libraries:

```bash
# Debian / Ubuntu
sudo apt install libx11-6 libxss1 libxext6

# Arch
sudo pacman -S libx11 libxss libxext
```

Python deps (`dbus-next`, `typing_extensions`) come with the package.

### From PyPI (wheel)

```bash
python3 -m pip install orcsome3
```

A GitHub Release publishes the **sdist and manylinux wheels** to PyPI (CPython **3.8 through the newest CPython cibuildwheel knows**, 3.15 as of cibuildwheel 4.2). Musllinux and free-threaded (`3.14t`, …) wheels are not built. No Windows/macOS. Bump the `pypa/cibuildwheel` pin in `.github/workflows/build-wheels.yml` when a new CPython ships.

### From this tree

First-time native build fetches git/tarball sources and compiles static libs. You need a C/C++ toolchain plus:

```bash
# Debian / Ubuntu
sudo apt install git cmake autoconf automake libtool pkg-config meson ninja-build \
  libx11-dev libxss-dev libxext-dev curl
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y   # resvg

# Arch
sudo pacman -S git cmake autoconf automake libtool pkgconf meson ninja \
  libx11 libxss libxext rust
```

Then:

```bash
git clone https://github.com/ahsand97/orcsome3.git
cd orcsome3
make native          # static libs + orcsome3_backend.so  (slow once)
python3 -m pip install .
```

`pip install .` **reuses** `orcsome3_built_libraries/`; it does not download those libs again. Run `make native` first on a clean clone.

Hacking without installing the package:

```bash
make dev             # venv + deps + native
make run             # python -m orcsome3  (needs ~/.config/orcsome3/rc.py)
```

## 🚀 Quick start

Create `~/.config/orcsome3/rc.py` (or pass `-c`). If the file is missing, orcsome3 logs an error and exits.

```python
from pathlib import Path

from orcsome3 import get_wm
from orcsome3.libs.xlib import XKeyEvent
from orcsome3.notify import Notification
from orcsome3.window_manager import Window, WindowManager, WindowMatchers

wm: WindowManager = get_wm()


@wm.on_key(key_definition="Control + b")
def on_pressed_hotkey(window: Window, event: XKeyEvent) -> None:
    # `window` is the grab window (root for a global hotkey). Focused client: wm.current_window
    print("Control + b was pressed")


@wm.on_manage(WindowMatchers(name="easyeffects", class_="easyeffects"))
def on_create_easyeffects() -> None:
    wm.event_window.set_icon(icon=Path("/path/to/icon.svg"))


@wm.on_property_change(property="_NET_WM_STATE")
def hide_title_bar_when_maximized() -> None:
    w = wm.event_window
    if w.maximized_horz and w.maximized_vert:
        if w.decorated:
            w.set_state(decorate=False)
    elif not w.decorated:
        w.set_state(decorate=True)


@wm.on_manage(WindowMatchers(name="Navigator", class_="firefox", window_type=["_NET_WM_WINDOW_TYPE_NORMAL"]))
def show_notification_firefox_open() -> None:
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

One process per `$DISPLAY` (lock under `$XDG_RUNTIME_DIR/orcsome3/`). Extra monitors on the same X server share that instance. A second X server (Chrome Remote Desktop, VNC, `:1`) is a separate process and does not steal grabs from `:0`. Saving the loaded `rc.py` reloads it (or send `SIGUSR1`). `SIGINT` / `SIGTERM` quit. A StatusNotifierItem tray icon (Reload / Quit menu) is registered when a SNI host is on the session bus.

Hotkeys: `"Control + d"` or a `KeyDefinition`. Modifiers: `Control`/`Ctrl`, `Alt`/`Meta`, `Shift`, `Win`/`Super`, `AnyModifier`. Keys are X keysym names (the `XK_` prefix stripped).

`@wm.on_create(...)` runs for windows already mapped at startup. `@wm.on_manage(...)` skips that sweep — use it when you nest `@wm.on_destroy` so you do not attach once per existing client.

## 🛠️ Develop

| Command | What it does |
| --- | --- |
| `make native` | Download/build static libs and compile the Cython backend |
| `make native-fast` | Re-cythonize/link only (needs a prior `native`) |
| `make native-rebuild` | Wipe the lib cache and rebuild |
| `make stubs` | Regenerate `orcsome3_backend.pyi` from the `.pyx` (needs the `.so`) |
| `make format` / `make lint` | ruff, mypy, basedpyright, extra checks, stub `--check` |
| `make clean` | Build artifacts, `orcsome3_built_libraries/`, `.so` |

Do not hand-edit generated `.c` files or `orcsome3_built_libraries/`.

`python -m orcsome3.libs.build --build-dir .` is the same as `make native`. `--dynamic` links system libev/gd/Magick instead of the static copies.

## 📄 License

MIT. See [LICENSE](LICENSE).
