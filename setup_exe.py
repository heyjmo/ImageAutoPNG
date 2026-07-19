"""
Legacy entry point — kept so old docs/scripts still work.

Prefer building via build_exe.py: ImageAutoPNG-Setup.exe is now the same
binary as ImageAutoPNG.exe (self-install by filename). Running this module
when frozen is not the primary path anymore.
"""

from __future__ import annotations

import sys

from installer import run_setup_and_exit


if __name__ == "__main__":
    if not getattr(sys, "frozen", False):
        print(
            "Use: python build_exe.py\n"
            "Then distribute release\\ImageAutoPNG-Setup.exe\n"
            "(self-installing copy of the app — does not extract nested exes)."
        )
        sys.exit(1)
    run_setup_and_exit()
