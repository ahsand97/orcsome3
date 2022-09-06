from cffi.api import FFI as FFI
from orcsome3.orcsome import utils as utils
from typing import List, Tuple

source: str
export_source: str
LIBRARIES: List[str]
compiler_args: Tuple[List[str], List[str]]
ffibuilder: FFI

def main(verbose: bool = ...) -> None: ...
