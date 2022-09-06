Orcsome3 is a port from python2 to python3 and rework of `orcsome <https://github.com/baverman/orcsome>`_, which is a scripting extension for NETWM compliant window managers.

Features
--------

* Written on python3. It means very hackable.

* Optimization, cpu and memory efficiency are top goals (cffi is used for xlib
  bindings).

* Extensive use of python3 syntax to provide easy and expressive eDSL in
  configuration script.

* Supports NETWM standards.

* Very thin wrapper around X. You can use existing xlib background.


Installation
------------

From PyPI
'''''''''
::

    python3 -m pip install orcsome3


From source
'''''''''''

::

   git clone --depth=1 git://github.com/ahsand97/orcsome3.git
   cd orcsome3
   python3 -m pip install .

---------------------------------------------------

Quick start
'''''''''''

Some of the functionalities offered are:
    - To bind global hot keys
    - To hide the title bar when a window is maximized
    - To change the icon of a window

Edit ``~/.config/orcsome3/rc.py``::

    from orcsome3.orcsome import get_wm
    from orcsome3.orcsome.wm import WM
    from orcsome3.orcsome.wrappers import Window
    from pathlib import Path

    wm: WM = get_wm()

    # Global hotkey
    @wm.on_key(keydef="Control + b")
    def on_pressed_hotkey() -> None:
        print("Control + b was pressed")

    # Change window icon
    @wm.on_manage(name="easyeffects", cls="easyeffects")
    def on_create_easyeffects() -> None:
        path_imagen: Path = Path("/my/other/icon/icon.svg")
        wm.event_window.set_window_icon(icon=path_imagen)

    # Hide title bar when a window is maximized
    @wm.on_property_change(properties=["_NET_WM_STATE"])
    def window_state_changed() -> None:
        if wm.event_window.maximized_horz and wm.event_window.maximized_vert:
            if wm.event_window.decorated:
                wm.set_window_state(window=wm.event_window, decorate=False)
        else:
            if not wm.event_window.decorated:
                wm.set_window_state(window=wm.event_window, decorate=True)

And start orcsome3. That's all.
