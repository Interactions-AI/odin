import argparse
import json
import yaml

from odin import LOGGER
from jinja2 import Template
from eight_mile.downloads import open_file_or_url
from mead.utils import parse_and_merge_overrides
from shortid import ShortId
import os.path
SHORT_ID = ShortId()

SUFFIX = '.yml.jinja2'


def main():
    """This should have auth around it."""
    parser = argparse.ArgumentParser(description="Convert a template and upload a job to odin")
    parser.add_argument('file', help='The template YAML file')

    args, overrides = parser.parse_known_args()

    params = parse_and_merge_overrides({}, overrides, pre='x')

    if not args.file.endswith(SUFFIX):
        raise Exception('Expected template YAML file')

    with open_file_or_url(args.file) as f:
        s = f.read()
        template = Template(s)
        output_s = template.render(**params)
        LOGGER.debug(output_s)
    yy = yaml.load(output_s, Loader=yaml.FullLoader)

    file_name = args.file.replace(SUFFIX, '.yml')
    with open(file_name, "w", encoding='utf-8') as wf:
        yaml.safe_dump(yy, wf)
        LOGGER.info("Wrote out %s", file_name)


if __name__ == "__main__":
    main()

