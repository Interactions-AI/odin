import os
import random
import string
from copy import deepcopy
from itertools import chain
from typing import Optional
from unittest.mock import patch
import pytest
from odin.generate import (
    ALWAYS,
    get_images,
    guess_export_loc,
    make_pipeline_dir,
    generate_mead_task,
    generate_chore_task,
    generate_export_task,
)


CHARS = list(chain(string.ascii_letters, string.digits))


def rand_str(length: Optional[int] = None, min_: int = 3, max_: int = 10):
    if length is None:
        length = random.randint(min_, max_)
    return ''.join([random.choice(CHARS) for _ in range(length)])


def test_all_export_in_config():
    export = {'output_dir': rand_str(), 'project': rand_str(), 'name': rand_str()}
    export_gold = deepcopy(export)
    config = {'export': export}
    export = guess_export_loc(config)
    assert export == export_gold


def test_override_export():
    output_dir = rand_str() if random.choice([True, False]) else None
    project = rand_str() if random.choice([True, False]) else None
    name = rand_str() if random.choice([True, False]) else None
    export = {'output_dir': output_dir or rand_str(), 'project': project or rand_str(), 'name': name or rand_str()}
    export_gold = {
        'output_dir': output_dir or export['output_dir'],
        'project': project or export['project'],
        'name': name or export['name'],
    }
    config = {'export': export}
    export = guess_export_loc(config)
    assert export == export_gold


def test_make_pipeline_error_on_clobber():
    with patch('odin.generate.os.path.exists') as e_patch:
        e_patch.return_value = True
        with pytest.raises(FileExistsError):
            make_pipeline_dir(rand_str(), rand_str(), rand_str(), clobber=False)


def test_make_pipeline_deletes():
    with patch('odin.generate.os.path.exists') as e_patch:
        e_patch.return_value = True
        root = rand_str()
        uname = rand_str()
        pipe = rand_str()
        pipeline = os.path.join(root, uname, pipe)
        with patch('odin.generate.shutil.rmtree') as rm_patch:
            with patch('odin.generate.os.makedirs') as make_patch:
                make_pipeline_dir(root, uname, pipe, clobber=True)
        rm_patch.assert_called_once_with(pipeline)
        make_patch.assert_called_once_with(pipeline)


def test_get_images_values():
    def test():
        defaults = {
            'mead-image': rand_str(),
            'odin-image': rand_str(),
            'template-image': rand_str(),
            'hpctl-image': rand_str(),
            'claim-name': rand_str(),
            'models-claim': rand_str(),
        }
        mead_override = None if random.choice([True, False]) else rand_str()
        odin_override = None if random.choice([True, False]) else rand_str()
        template_override = None if random.choice([True, False]) else rand_str()
        hpctl_override = None if random.choice([True, False]) else rand_str()
        claim_override = None if random.choice([True, False]) else rand_str()
        models_override = None if random.choice([True, False]) else rand_str()

        with patch('odin.generate.read_config_file') as read_patch:
            read_patch.return_value = defaults
            images, claims = get_images(rand_str(), mead_override, odin_override, claim_override, models_override)
            assert images['mead'] == mead_override or defaults['mead-image']
            assert images['odin'] == odin_override or defaults['odin-image']
            assert images['template'] == odin_override or defaults['template-image']
            assert images['hpctl'] == odin_override or defaults['hpctl-image']
            assert claims['data'] == claim_override or defaults['claim-name']
            assert claims['models'] == models_override or defaults['models-claim']

    for _ in range(100):
        test()


def test_get_images_location():
    loc = rand_str()
    defaults = {
        'mead-image': rand_str(),
        'odin-image': rand_str(),
        'template-image': rand_str(),
        'hpctl-image': rand_str(),
        'claim-name': rand_str(),
        'models-claim': rand_str(),
    }
    with patch('odin.generate.read_config_file') as read_patch:
        read_patch.return_value = defaults
        get_images(loc)
        read_patch.assert_called_once_with(f"{loc}/images.yml")


@pytest.fixture
def depends_data():
    depends_len = random.randint(0, 2)
    if depends_len == 0:
        depends = None
        depends_gold = None
    else:
        if depends_len == 1 and random.choice([True, False]):
            depends = rand_str()
            depends_gold = [depends]
        else:
            depends = [rand_str() for _ in range(depends_len)]
            depends_gold = deepcopy(depends)
    return depends, depends_gold


def test_generate_mead_task_values(depends_data):
    def test():
        datasets_default = 'datasets.yml'
        embeddings_default = 'embeddings.yml'
        template = {
            'name': None,
            'image': None,
            'num_gpus': None,
            'mount': {'claim': None},
            'depends': None,
            'args': ['--config', 'config-{{config-name}}'],
        }

        task_name = rand_str()
        config_name = rand_str()
        mead_image = rand_str()
        claim = rand_str()
        datasets = None
        datasets_gold = datasets_default
        gold_args = ['--config', config_name]
        if random.choice([True, False]):
            datasets = rand_str()
            datasets_gold = datasets
            gold_args.extend(['--datasets', datasets_gold])
        embeddings = None
        embeddings_gold = embeddings_default
        if random.choice([True, False]):
            embeddings = rand_str()
            embeddings_gold = embeddings
            gold_args.extend(['--embeddings', embeddings_gold])
        depends, depends_gold = depends_data

        gpus = random.randint(0, 16)

        gold = {
            'name': task_name,
            'image': mead_image,
            'num_gpus': gpus,
            'mount': {'claim': claim},
            'depends': depends_gold,
            'args': gold_args,
            'pull_policy': ALWAYS,
        }

        mead_task = generate_mead_task(
            template,
            task_name,
            config_name,
            mead_image,
            claim,
            datasets,
            embeddings=embeddings,
            depends=depends,
            gpus=gpus,
        )

        assert mead_task == gold

    for _ in range(100):
        test()


def test_genereate_chore_task_values(depends_data):
    def test():
        template = {'image': None, 'mount': {'claim': None}}

        image = rand_str()
        claim = rand_str()
        depends, depends_gold = depends_data

        gold = {'image': image, 'mount': {'claim': claim}, 'pull_policy': ALWAYS}
        if depends:
            gold['depends'] = depends_gold

        chore_task = generate_chore_task(template, image, claim, depends)

        assert chore_task == gold

    for _ in range(100):
        test()


# def test_generate_export_task(depends_data):
#     def test():
#         template = {
#             'image': None,
#             'mounts': [{'claim': None}],
#             'args': [
#                 '--config',
#                 'config-{{config-name}}',
#                 '--task',
#                 '{{task-name}}',
#                 '--dataset',
#                 '{{dataset-name}}',
#                 '--type',
#                 '{{type-name}}',
#                 '--datasets',
#                 'datasets.yml',
#                 '--metric',
#                 '{{metric-name}}',
#                 '--models',
#                 '{{model-placeholder}}',
#             ],
#         }

#         image = rand_str()
#         claim = rand_str()
#         task = rand_str()
#         datasets = None
#         datasets_gold = 'datasets.yml'
#         if random.choice([True, False]):
#             datasets = rand_str()
#             datasets_gold = datasets
#         config_name = rand_str()
#         dataset_name = rand_str()
#         depends, depends_gold = depends_data
#         if depends is None:
#             depends = rand_str()
#             depends_gold = [depends]
#         metric = rand_str()
#         export_type = rand_str()

#         gold = {
#             'image': image,
#             'mounts': [{'claim': claim}],
#             'args': [
#                 '--config',
#                 f"config-{config_name}",
#                 '--task',
#                 task,
#                 '--dataset',
#                 dataset_name,
#                 '--type',
#                 export_type,
#                 '--datasets',
#                 datasets_gold,
#                 '--metric',
#                 metric,
#                 '--models',
#             ],
#             'depends': depends_gold,
#             'pull_policy': ALWAYS,
#         }
#         gold['args'] += ['${PIPE_ID}--' + dep for dep in reversed(depends_gold)]

#         mead_export = generate_export_task(
#             template, image, claim, task, datasets, dataset_name, config_name, depends, metric, export_type
#         )

#         assert mead_export == gold

#     for _ in range(100):
#         test()


def test_generate_export_no_export():
    mead_export = generate_export_task({}, None, None, None, None, None, None, None, export_policy=None)
    assert mead_export == {}
