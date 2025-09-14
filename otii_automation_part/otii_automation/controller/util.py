import json
import logging
import os

from paramiko.client import SSHClient, AutoAddPolicy
from scp import SCPClient
from ..environment import Environment as Env

logger = logging.getLogger('controller')


def download_results(trace) -> dict:
    """ Download results from server """
    try:
        with SSHClient() as ssh:
            ssh.set_missing_host_key_policy(AutoAddPolicy())
            ssh.connect(
                hostname=Env.config['server']['host'],
                username=Env.config['server']['username'],
                key_filename=Env.config['server']['key_file']
            )

            with SCPClient(ssh.get_transport()) as scp:
                scp.get(Env.config['server']['path'] + f'{trace}.json', '.tmp.json')

            with open('.tmp.json') as fp:
                device_res = json.load(fp)

        os.remove('.tmp.json')
        return device_res
    except Exception as ex:
        logger.warning(f'Download results {trace} failed: {ex}')
        raise ex


def download_device_logs() -> None:
    try:
        with SSHClient() as ssh:
            ssh.set_missing_host_key_policy(AutoAddPolicy())
            ssh.connect(
                hostname=Env.config['server']['host'],
                username=Env.config['server']['username'],
                key_filename=Env.config['server']['key_file']
            )

            with SCPClient(ssh.get_transport()) as scp:
                scp.get(Env.config['server']['path'] + f'device.log', os.path.join(Env.log_dir, 'device.log'))

    except Exception as ex:
        logger.warning(f'Download logs failed: {ex}')
        raise ex


def build_config_message(params: dict, trace: str) -> dict:
    """ Build experiment configuration for the device """

    # Build JSON message and dump to string

    configuration = {
        'experiment': Env.config['meta']['experiment'],
        'host': Env.config['server']['host'],
        'port': Env.config['server']['port'],
        'payload_size': params['payload_size'],
        'radio_generation': params['radio_generation'],
        'bandwidth': params['bandwidth'],
        'delay': params['delay'],
        'results_dir': f'results/{Env.timestamp}/{trace}',
    }

    return configuration


def build_trace_name(params: dict) -> str:
    """ Build trace name from configuration """

    trace_name = f'{Env.trace_counter}_{params["delay"]}S_{params["bandwidth"].split("%")[0]}_' \
                 f'{params["radio_generation"]}_{params["payload_size"]}'

    trace_name += f'_{Env.iteration:03d}'

    return trace_name
