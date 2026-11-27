"""Backwards-compatible entry point for the packaged fixture builder.

The builder and its sources now live inside ``modfilegen`` so that a plain
``pip install`` can build a database without a repository checkout, which is
what ``agriscale selftest`` relies on. This keeps the path the tests and the
documented command line already use.
"""

import sys

from modfilegen.fixtures import *  # noqa: F401,F403
from modfilegen.fixtures import (  # noqa: F401
    CELSIUS_V32_TEMPLATE_SOURCES,
    CULTIVARS_DIR,
    FIXTURES,
    MASTERINPUT_SOURCES,
    MODELSDICTIONARY_SOURCES,
    SOURCES_DIR,
    build_celsius_v32_template,
    build_masterinput,
    build_modelsdictionary,
    export_celsius_v32_template,
    export_masterinput,
    export_modelsdictionary,
    main,
)

if __name__ == "__main__":
    main(sys.argv[1:])
