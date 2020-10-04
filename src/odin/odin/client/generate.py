"""Websocket client to generate a config."""
import argparse
import asyncio
import getpass
import json
import websockets

from baseline.utils import str2bool
from odin import LOGGER, APIField, APIStatus
from odin.client import ODIN_URL, ODIN_PORT
from odin.generate import preprocess_arguments, ALWAYS, IF_NOT_PRESENT, NEVER


async def request_generate_config(ws, config):
    """Use async to open a connection to serve.py and generate a config."""
    async with websockets.connect(ws) as websocket:
        await websocket.send(json.dumps({APIField.COMMAND: 'GENERATE', APIField.REQUEST: config}))

        result = json.loads(await websocket.recv())
        if result[APIField.STATUS] == APIStatus.ERROR:
            LOGGER.error(result)
            return
        if result[APIField.STATUS] == APIStatus.OK:
            LOGGER.info('Generated pipeline is called %s', result[APIField.RESPONSE])


def main():
    """Use `asyncio` to connect to a websocket and request the creation of a pipeline config."""
    parser = argparse.ArgumentParser()
    parser.add_argument("configs", nargs="+", help="The path to the mead config we want to turn into a pipeline.")
    parser.add_argument("--host", default=ODIN_URL, help="The hostname of the odin server.")
    parser.add_argument("--port", default=ODIN_PORT, help="The port of the odin server.")
    parser.add_argument(
        '--scheme',
        choices={'wss', 'ws'},
        default='wss',
        help='Websocket connection protocol, use `wss` for remote connections and `ws` for localhost',
    )
    parser.add_argument("--user", default=getpass.getuser(), help="The prefix of your pipeline name.")
    parser.add_argument(
        "--pipeline-name", "--pipeline_name", help="The name of your pipeline. Defaults to the name of the mead config."
    )
    parser.add_argument("--datasets", help="The location of your custom datasets index file.")
    parser.add_argument("--embeddings", help="The location of you custom embeddings file.")
    parser.add_argument("--train-file", "--train_file", help="The location of a custom train file")
    parser.add_argument("--valid-file", "--valid_file", help="The location of a custom valid file")
    parser.add_argument("--test-file", "--test_file", help="The location of a custom test file")
    parser.add_argument("--task", help="The baseline task for this model")
    parser.add_argument(
        "--models",
        type=int,
        default=1,
        help="The number of times to train the model (or the number of models to train when using hpctl).",
    )
    parser.add_argument("--gpus", type=int, help="The number of GPUs to give to each model training task.")
    parser.add_argument("--metric", default="acc", help="The name of the metric used to compare the results of models.")
    # Including --export-type for back compat
    parser.add_argument(
        "--export-policy",
        "--export_policy",
        "--export-type",
        default=None,
        help="The type of decision to use when deciding if a model should be exported.",
    )
    parser.add_argument(
        "--slack",
        type=str2bool,
        default=True,
        help="Should we send a slack message when the pipeline has finished running?",
    )
    parser.add_argument(
        "--slack-web-hook", "--slack_web_hook", default=None, help="The endpoint for slack messages to go to"
    )
    # parser.add_argument("--git-commit", "--git_commit", type=str2bool, default=False,
    #                     help="Should we commit the exported model with git?")
    parser.add_argument("--mead-image", "--mead_image", help="The name of the image to use for mead training.")
    parser.add_argument(
        "--odin-image", "--odin_image", help="The name of the image to use for odin exporting and odin chores."
    )
    parser.add_argument("--claim-name", "--claim_name", help="The name of the k8s pvc claim.")
    parser.add_argument(
        "--pull-policy",
        "--pull_policy",
        help="The pull policy to use for containers",
        choices={IF_NOT_PRESENT, ALWAYS, NEVER},
        default=ALWAYS,
    )
    parser.add_argument("--clobber", type=str2bool, default=True, help="Should we overwrite a previous pipeline?")
    parser.add_argument("--output-dir", "--output_dir", help="The base dir for where a model should be exported.")
    parser.add_argument("--project", help="The name of the project this model is for.")
    parser.add_argument("--name", help="The name of the model, i.e. intent, sf, etc.")
    parser.add_argument('--modules', help='modules to load', default=[], nargs='+', required=False)
    parser.add_argument('--mead-eval-dataset', "--mead_eval_dataset", help="The dataset to use for mead-eval")
    parser.add_argument('--template', help='An odin-template sample file.')
    parser.add_argument('--hpctl', help='Should hpctl be used in the pipeline to sample configs', action="store_true")
    parser.add_argument('--seed', help='A seed for controlling hpctl', type=int)
    args = parser.parse_args()

    config = preprocess_arguments(args)

    ws = f'{args.scheme}://{args.host}:{args.port}'
    asyncio.get_event_loop().run_until_complete(request_generate_config(ws, config))


if __name__ == "__main__":
    main()
