"""Allow `python -m lessonforge`.

Kept alongside the `lessonforge` console script because editable installs are
not universally reliable — some Python builds skip `__editable__*.pth` files,
which leaves the console script installed but the package unimportable. Running
as a module works whenever the package is on `sys.path` by any means, including
a plain `PYTHONPATH=src`.
"""

from .cli import main

if __name__ == "__main__":
    main()
