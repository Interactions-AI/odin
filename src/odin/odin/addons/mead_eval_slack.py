"""A chore that summarizes and notifies the mead eval performance."""

import os
from typing import Dict
from string import Template
import requests
import pandas as pd
from odin.chores import register_chore


@register_chore('slack-eval-report-intent')
def slack_webhook_mead_eval_intent(parent_details: Dict, webhook: str, template: str, base_dir: str) -> None:
    """Substitute a template message and post to slack

    :param parent_details: The context to use to replace values in the template.
    :param webhook: The webhook key
    :param template: The message.
    :param base_dir: the base dir to read result files from
    """

    message: str = Template(template).substitute(parent_details)
    mismatched_jobs = []
    for job_id in parent_details['executed']:
        if 'mead-eval' in job_id:
            df = pd.read_csv(os.path.join(base_dir, f'{job_id}.tsv'), header=None, sep='\t')
            mismatched = df[df[1] != df[2]].copy()
            mismatched.insert(0, 'job_id', job_id)
            message = message + f'\n[[job_id]] {job_id} [[failures]]: {len(mismatched)}'
            os.remove(os.path.join(base_dir, f'{job_id}.tsv'))
            mismatched_jobs.append(mismatched)
    if mismatched_jobs:
        pd.concat(mismatched_jobs).to_csv(os.path.join(base_dir, 'results.csv'))
    requests.post(webhook, json={"text": message})
