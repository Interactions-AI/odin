"""Tools to manipulate YAML
"""
import argparse
import json
import os
from typing import Dict, TextIO, Union
import yaml

from baseline.utils import str_file, str2bool


Path = str


@str_file(data='r', out='w')
def yaml_to_json(data: str, out: str, indent: int = 2) -> None:
    """Convert a YAML file into a JSON file

    :param data: The file to read from
    :param out: The file to write to
    :param indent: The indentation
    """
    json.dump(yaml.load(data, Loader=yaml.FullLoader), out, indent=indent)


@str_file(data='r', out='w')
def json_to_yaml(
    data: Union[Path, TextIO], out: Union[Path, TextIO], indent: int = 2, default_flow: bool = False
) -> None:
    """Convert a JSON file into a YAML file.

    :param data: The file to read from
    :param out: The file to write to
    :param indent: The indentation to use in the output
    :param default_flow: Should the yaml lists be inlined?
    """
    yaml.dump(json.load(data), out, indent=indent, default_flow_style=default_flow)


@str_file(file_path="w")
def write_yaml(content: Dict, file_path: Union[Path, TextIO]) -> None:
    """write data out to a yaml file.

    :param content: The data to be written.
    :param file_path: The file to write to.
    """
    yaml.dump(content, file_path, default_flow_style=False)


def main():
    """Convert a YAML file to JSON"""
    parser = argparse.ArgumentParser(description="Convert a yaml file to json.")
    parser.add_argument("file", help="The yaml file.")
    parser.add_argument("--indent", help="Number of spaces to indent in json.", default=2, type=int)
    parser.add_argument("--out", help="The name of the output file")
    args = parser.parse_args()

    if args.out is None:
        base, _ = os.path.splitext(args.file)
        args.out = f"{base}.json"

    yaml_to_json(args.file, args.out, indent=args.indent)


def json_main():
    """Convert a JSON file to YAML"""
    parser = argparse.ArgumentParser(description="Convert a json file to yaml.")
    parser.add_argument("file", help="The yaml file.")
    parser.add_argument("--indent", help="Number of spaces to indent in yaml.", default=2, type=int)
    parser.add_argument("--out", help="The name of the output file")
    parser.add_argument(
        "--default-flow", help="Should you use the yaml flow were lists are inline", default=False, type=str2bool
    )
    args = parser.parse_args()

    if args.out is None:
        base, _ = os.path.splitext(args.file)
        args.out = f"{base}.yml"

    json_to_yaml(args.file, args.out, indent=args.indent, default_flow=args.default_flow)
