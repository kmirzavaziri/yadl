import argparse
from glob import glob
from os import path
from sys import stderr

from yadl.datatypes import Args, CodeItem, Memory
from yadl.visitors import FilesVisitor


def parse_arguments() -> Args:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_dir", type=str, help="Project Directory")
    parser.add_argument("_", help="Ignore pre-commit args", nargs="*")

    args = parser.parse_args()

    return Args(project_dir=args.project_dir)


def main():
    args = parse_arguments()

    filenames = glob(path.join(args.project_dir, "**", "*.py"), recursive=True)

    memory = Memory()

    FilesVisitor.visit(filenames, memory)

    errors = CodeItem.render(CodeItem.remove_ignored(memory.get_unused_items()))

    if errors:
        print(errors, file=stderr)
        exit(1)


if __name__ == "__main__":
    main()
