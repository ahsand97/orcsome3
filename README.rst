Orcsome3 is a rework of `orcsome <https://github.com/baverman/orcsome>`_, which is a scripting extension for NETWM compliant window managers.

Features
--------

* Written on python3 fully compatyble with python type hints (`PEP 483 <https://peps.python.org/pep-0483/>`_) and mypy.
* Optimization, cpu and memory efficiency are top goals (`cffi <https://cffi.readthedocs.io/>`_ is used for xlib bindings).
* Extensive use of python3 syntax and documentation to provide easy and expressive way of creating the rules script.
* Supports NETWM standards.
* Very thin wrapper around X. You can use existing xlib background.


Installation
------------

Before installing orcsome3 it is necessary to have the build dependencies installed:

orcsome3 uses the following libraries:

* **libev**: Full-featured and high-performance event loop
* **Xlib**: (Also known as libX11) X Window System Protocol client library
* **Xss**: X Screen Saver extension client library
* **Xext**: Misc X Extension Library
* **gd**: GD graphics library
* **MagickWand**: C API for ImageMagick

To install them:

Debian/Ubuntu
'''''''''''''
.. code-block:: bash

    sudo apt install libev-dev libx11-dev libxss-dev libxext-dev libxtst-dev libgd-dev

It is necessary to install ImageMagick (version >= 7) from source since the official repositories as of Ubuntu 18.04 and Ubuntu 22.04 have the version 6.

.. code-block:: bash

    sudo apt remove -y imagemagick imagemagick-6-common # Remove ImageMagick 6 if installed
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
.. code-block:: bash

    sudo pacman -S libev libx11 libxss libxext libxtst imagemagick gd


For more information about ImageMagick installation go to `ImageMagick official installation page <https://imagemagick.org/script/download.php>`_.

After installing the build dependencies, orcsome3 can be installed:
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

From PyPI
'''''''''
.. code-block:: bash

    python3 -m pip install orcsome3


From source
'''''''''''

.. code-block:: bash

   git clone https://github.com/ahsand97/orcsome3.git
   cd orcsome3
   python3 -m pip install .

**orcsome3 installs an executable script "orcsome3" located in** ``~/.local/bin/orcsome3`` **at a user level
or in** ``/usr/bin/orcsome3`` **if it was installed as root**

---------------------------------------------------

Quick start
'''''''''''

Some of the functionalities offered are:

* To bind global hot keys
* To hide the title bar when a window is maximized
* To change the icon of a window
* Show desktop notification

Edit ``~/.config/orcsome3/rc.py``:

.. code-block:: python

    from orcsome3 import get_wm
    from orcsome3.notify import Notification
    from orcsome3.window_manager import WindowManager, WindowMatchers
    from pathlib import Path

    wm: WindowManager = get_wm()

    # Global hotkey
    @wm.on_key(keydef="Control + b")
    def on_pressed_hotkey() -> None:
        print("Control + b was pressed")

    # Change window icon
    @wm.on_manage(WindowMatchers(name="easyeffects", cls="easyeffects"))
    def on_create_easyeffects() -> None:
        path_image: Path = Path("/path/to/my/other/icon.svg")
        wm.event_window.set_icon(icon=path_image)

    # Hide title bar when a window is maximized
    @wm.on_property_change(property="_NET_WM_STATE")
    def hide_title_bar_when_maximized() -> None:
        if wm.event_window.maximized_horz and wm.event_window.maximized_vert:
            if wm.event_window.decorated:
                wm.event_window.set_state(decorate=False)
        else:
            if not wm.event_window.decorated:
                wm.event_window.set_state(decorate=True)

    # Show desktop notification
    @wm.on_manage(WindowMatchers(name="Navigator", cls="firefox", window_type=['_NET_WM_WINDOW_TYPE_NORMAL']))
    def show_notification_firefox_open() -> None:
        Notification(
            app_name="Firefox",
            summary="Firefox is now open!",
            body="<b>Notification body!!!<b>",
            actions=[Notification.Action(visible_name="Action #1", callback=lambda: print("Action #1 callback"))],
            on_close=lambda: print("My notification was closed"),
            hints=Notification.Hints(urgency=Notification.Hints.Urgency.NORMAL),
            show=True,
        )

And start ``orcsome3``. That's all.
