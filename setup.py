import sys
from pathlib import Path

from setuptools import setup
from setuptools.extension import Extension

from orcsome3.libs.setup import build_extensions
from orcsome3.utils import rmdir


def generate_stubs() -> None:  # FALTA
    """This function re-generate the stubs for orcsome3, only meant to be used for development"""
    try:

        def generate_files() -> Path:
            """Generate stubs using mypy. Output folder is `./orcsome3-stubs`"""
            import mypy.stubgen as stubgen

            # ./orcsome3-stubs
            output_dir = Path(__file__).parent.joinpath("orcsome3-stubs")

            # Delete folder if already exists
            rmdir(output_dir)

            # Create output folder
            output_dir.mkdir(parents=True, exist_ok=True)

            # Create __init__.py file to initialize module within the output folder
            output_dir.joinpath("__init__.py").touch(exist_ok=True)

            # Args for mypy
            source_files: Path = Path(__file__).parent.joinpath("orcsome3")
            args = ["--include-private", "--verbose", "--output", str(output_dir), str(source_files)]
            sys.argv.extend(args)

            # This will run "stubgen --verbose --output ./orcsome3-stubs ./orcsome3"
            stubgen.main()

            # return the full path of ./orcsome3-stubs
            return output_dir

        def copy_files(source: Path, target: Path, delete_source: bool = False) -> None:
            """
            Copy all the files in `source` to `target`. `delete_source` denote if remove source folder or not
            """
            import shutil

            for file_ in source.iterdir():
                # Copy every single file from ./orcsome3-stubs/orcsome3 to ./orcsome3-stubs
                if file_.is_file():
                    shutil.copy(src=file_, dst=target.joinpath(file_.name))
                if file_.is_dir():
                    shutil.copytree(src=file_, dst=target.joinpath(file_.name), dirs_exist_ok=True)
            if delete_source:
                rmdir(source)  # remove recursively ./orcsome3-stubs/orcsome3

        def complete_stubs(dir: Path) -> None:
            """
            This function will edit every .pyi file and replace the type Incomplete
            for the type Any, also, it will put the decorator @cached_property to the
            necessary methods accordingly to source
            """
            files_to_edit: list[Path] = []

            # Add every .pyi file that has the type "Incomplete" or the decorator
            # @functools.cached_property to the list of files to edit
            for file_ in dir.iterdir():
                if not file_.name.endswith(".pyi"):
                    continue
                with file_.open(mode="r") as content:
                    lines = content.readlines()
                    for line in lines:
                        if (
                            "from _typeshed import Incomplete" in line
                            or "from functools import cached_property" in line
                        ):
                            files_to_edit.append(file_)
                            break

            source_files_folder = Path(__file__).parent.joinpath("orcsome3")
            for file_ in files_to_edit:
                src: Path = source_files_folder.joinpath(file_.name.replace(".pyi", ".py"))
                src_content: list[str] = []
                new_content: list[str] = []
                typing_import_src: str = ""

                with src.open(mode="r") as src_:
                    src_content = src_.readlines()
                    for line in src_content:
                        if "from typing import" in line:
                            typing_import_src = "from typing import " + ", ".join(
                                [x for x in line.replace("from typing import ", "").split(sep=", ") if x[0].isupper()]
                            )
                            break

                with file_.open(mode="r") as f_:
                    new_content = [line for line in f_.readlines() if "from _typeshed import Incomplete" not in line]
                    fix_decorator: bool = False
                    list_variables_cached: list[str] = []
                    for index, line in enumerate(iterable=new_content):
                        line_clean: str = line.translate(str.maketrans("", "", " \n\t\r"))
                        if "from typing import" in line:
                            new_content[index] = f"{typing_import_src}\n"
                        if ":Incomplete" in line_clean:
                            nombre_variable: str = line_clean.split(sep=":")[0]
                            line_fixed: bool = False
                            for src_line in src_content:
                                if f"self.{nombre_variable}:" in src_line:
                                    variable_definition: list[str] = src_line.strip().lstrip().split(sep=":")
                                    if not len(variable_definition) >= 2:
                                        continue
                                    if variable_definition[1].strip():
                                        new_content[index] = line.replace(
                                            "Incomplete", variable_definition[1].split(sep="=")[0].strip()
                                        )
                                        line_fixed = True
                                        break
                            if not line_fixed:
                                new_content[index] = line.replace("Incomplete", "Any")
                        if "from functools import cached_property" in line:
                            fix_decorator = True
                            for index, src_line in enumerate(iterable=src_content):
                                if "@cached_property" in src_line:
                                    list_variables_cached.append(src_content[index + 1])
                        if fix_decorator and line.replace(" ...", "") in list_variables_cached:
                            new_content[index] = f"    @cached_property\n{line}"

                with file_.open(mode="w") as f_:
                    f_.writelines(new_content)

        output_dir: Path = generate_files()  # ./orcsome3-stubs
        copy_files(source=output_dir.joinpath("orcsome3"), target=output_dir, delete_source=True)
        complete_stubs(dir=output_dir)
    except ModuleNotFoundError as e:
        print(f"Exception creating stubs: {e}")


if "--generate-stubs" in sys.argv:
    sys.argv.remove("--generate-stubs")
    generate_stubs()
    exit()

extensions: list[Extension] = build_extensions(skip_build=True, static=True)[1]  # Cythonize extensions
# Everything else is defined in the file pyproject.toml
setup(  # type: ignore[reportUnusedCallResult]
    package_data={"orcsome3.libs.xlib": ["*.pxd", "*.pyx"], "orcsome3-stubs": ["*.pyi"]},
    include_package_data=False,
    ext_modules=extensions,
)
