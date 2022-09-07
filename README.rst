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

Before installing orcsome3 it is necessary to have the build dependencies installed:

orcsome3 uses the following libraries:

    - libev: Full-featured and high-performance event loop
    - X11
    - Xss: X11 Screen Saver extension client library
    - Xext: Misc X Extension Library
    - gd: GD graphics library
    - MagickWand: C API for ImageMagick

To install them:

Debian/Ubuntu
'''''''''''''
::

    sudo apt install libev-dev libx11-dev libxss-dev libxext-dev libgd-dev

It is necessary to install ImageMagick7 from source::

    sudo apt remove -y imagemagick imagemagick-6-common
    sudo apt build-dep -y imagemagick
    wget https://imagemagick.org/archive/ImageMagick.tar.gz
    mkdir -p ./ImageMagick7
    tar xvzf ImageMagick.tar.gz --directory ./ImageMagick7 --strip-components=1
    cd ImageMagick7
    ./configure
    make
    sudo make install
    sudo ldconfig /usr/local/lib

Arch Linux
''''''''''
::

    sudo pacman -S libev libx11 libxss libxext imagemagick

After installing the build dependencies, orcsome3 can be installed:
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

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

**orcsome3 installs an executable script** "``orcsome3``" **located in** ``~/.local/bin/orcsome3`` **at a user level
or in** ``/usr/bin/orcsome3`` **if it was installed as root**

---------------------------------------------------

Quick start
'''''''''''

Some of the functionalities offered are:

    - To bind global hot keys
    - To hide the title bar when a window is maximized
    - To change the icon of a window

Edit ``~/.config/orcsome3/rc.py``:

.. code-block:: python

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

And start ``orcsome3``. That's all.
