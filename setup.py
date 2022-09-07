import sys
from typing import List

from setuptools import setup

import orcsome3.orcsome as orcsome3


def generate_stubs() -> None:
    try:
        from pathlib import Path

        def rmdir(directory: Path) -> None:
            """Delete all items from a directory"""
            directory = Path(directory)
            for item in directory.iterdir():
                if item.is_dir():
                    rmdir(directory=item)
                else:
                    item.unlink()
            directory.rmdir()

        def generate_files() -> Path:
            import mypy.stubgen as stubgen

            def initialize_modules(directory: Path) -> None:
                directory.mkdir(parents=True, exist_ok=True)
                directory.joinpath("__init__.py").touch(exist_ok=True)
                inner_directory = directory.joinpath("orcsome")
                inner_directory.mkdir(parents=True, exist_ok=True)
                inner_directory.joinpath("__init__.py").touch(exist_ok=True)

            output_dir = Path(__file__).parent.joinpath("orcsome3-stubs")
            if output_dir.is_dir():
                rmdir(directory=output_dir)
            initialize_modules(directory=output_dir)
            args = ["--verbose", "--output", str(output_dir), str(Path(__file__).parent.joinpath("orcsome3"))]
            sys.argv.extend(args)
            stubgen.main()
            return output_dir

        def copy_files(dir: Path) -> Path:
            import shutil

            destiny: Path = dir.joinpath("orcsome")
            for file_ in dir.joinpath("orcsome3", "orcsome").iterdir():
                shutil.copy(src=file_, dst=destiny.joinpath(file_.name))
            rmdir(directory=dir.joinpath("orcsome3"))
            return destiny

        def complete_stubs(dir: Path) -> None:
            files_to_edit: List[Path] = []
            for file_ in dir.iterdir():
                if file_.name.endswith(".pyi"):
                    with file_.open(mode="r") as content:
                        lines = content.readlines()
                        for line in lines:
                            if (
                                "from _typeshed import Incomplete" in line
                                or "from functools import cached_property" in line
                            ):
                                files_to_edit.append(file_)
                                break

            source_files = Path(__file__).parent.joinpath("orcsome3", "orcsome")
            for file_ in files_to_edit:
                src: Path = source_files.joinpath(file_.name.replace(".pyi", ".py"))
                src_content: List[str] = []
                new_content: List[str] = []
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
                    list_variables_cached: List[str] = []
                    for index, line in enumerate(iterable=new_content):
                        line_clean: str = line.translate(str.maketrans("", "", " \n\t\r"))
                        if "from typing import" in line:
                            new_content[index] = f"{typing_import_src}\n"
                        if ":Incomplete" in line_clean:
                            nombre_variable: str = line_clean.split(sep=":")[0]
                            line_fixed: bool = False
                            for src_line in src_content:
                                if f"self.{nombre_variable}:" in src_line:
                                    variable_definition: List[str] = src_line.strip().lstrip().split(sep=":")
                                    if not len(variable_definition) >= 2:
                                        continue
                                    if variable_definition[1].strip():
                                        new_content[index] = line.replace(
                                            "Incomplete", variable_definition[1].split("=")[0].strip()
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

        output_dir: Path = generate_files()
        stub_dir: Path = copy_files(dir=output_dir)
        complete_stubs(dir=stub_dir)
    except ModuleNotFoundError as e:
        print(f"EXCEPTION: {e}")


if "--generate-stubs" in sys.argv:
    sys.argv.remove("--generate-stubs")
    generate_stubs()
    exit()

setup(
    name="orcsome3",
    version=orcsome3.VERSION,
    author="Ahsan Pérez",
    author_email="ahsand.perez@gmail.com",
    description="Scripting extension for NETWM compliant window managers",
    long_description=open(file="README.rst").read(),
    long_description_content_type="text/x-rst",
    zip_safe=False,
    packages=["orcsome3.orcsome", "orcsome3-stubs.orcsome"],
    package_data={"orcsome3-stubs.orcsome": ["*.pyi", "**/*.pyi"]},
    include_package_data=True,
    cffi_modules=["orcsome3/orcsome/ev_build.py:ffibuilder", "orcsome3/orcsome/xlib_build.py:ffibuilder"],
    setup_requires=["cffi>=1.0.0"],
    install_requires=["cffi>=1.0.0"],
    scripts=["orcsome3/bin/orcsome3"],
    url="https://github.com/ahsand97/orcsome3",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Development Status :: 4 - Beta",
        "Environment :: X11 Applications",
        "Topic :: Desktop Environment :: Window Managers",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "Natural Language :: English",
    ],
    python_requires=">=3.8",
)
