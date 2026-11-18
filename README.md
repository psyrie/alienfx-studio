# AlienFX Studio

A local Flask interface for AlienFX lighting. The supported USB controller
implementation and its bundled data live in this project under `alienfx/`

## Install

For a per-user Linux install, extract the release archive and run:

```sh
./install.sh
```

This copies the app into `${XDG_DATA_HOME:-~/.local/share}/alienfx-studio`,
creates a Python virtual environment there, installs the Python dependencies,
and adds an AlienFX Studio entry to the user's applications menu. It does not
use `sudo`, install a system service, or start automatically at login. The
first install needs network access to download Python dependencies.

When finished, use the **Quit** control in Studio to stop the local server.
Uninstall with `uninstall.sh` from the installed app directory; saved palettes
and controller settings under `~/.config/alienfx-studio` are preserved.

To create a shareable source archive from this checkout:

```sh
./package-release.sh
```

The archive excludes virtual environments and build caches. An AppImage is
possible, but this user-local archive install is simpler to audit and update;
either format still relies on the host's USB device permissions.

## Run From Source

From this directory:

```sh
./run.sh
```

The script creates `.venv` here and installs Flask, Waitress, and PyUSB into
that environment. The controller package is already included in this project.
The studio opens at `http://127.0.0.1:8765`; stop it with the Quit control or
Ctrl+C.

The account running the studio still needs permission to access the AlienFX USB
device. A missing PyUSB or controller error is shown as a disconnected state;
the app does not run a zone scan.

### USB permissions

The bundled controller package includes
`alienfx/data/etc/udev/rules.d/10-alienfx.rules`. If the studio detects the
controller but reports `Access denied`, install or reload that rule and
re-trigger only the 13 R3 device:

```sh
sudo udevadm control --reload-rules
sudo udevadm trigger --action=add --subsystem-match=usb --attr-match=idVendor=187c --attr-match=idProduct=0529
```

Use `lsusb -d 187c:0529` to find the current bus/device number, then verify its
`/dev/bus/usb/BBB/DDD` node has mode `666`. Restart the studio with
`./run.sh` after the permission change. Do not run the studio itself as root.
