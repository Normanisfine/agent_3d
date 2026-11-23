"""Indoor room reconstruction with Agen3D."""
from pathlib import Path

__version__ = "0.1.0"

# Resolve the original offline module paths used by saved jobs and scripts.
__path__.append(str(Path(__file__).with_name("archive")))
