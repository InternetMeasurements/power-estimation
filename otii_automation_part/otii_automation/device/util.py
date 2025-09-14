import json
import logging
import os
import subprocess
import time
import RPi.GPIO as GPIO

import ifcfg

from string import ascii_letters

from .at_command import send_commands

logger = logging.getLogger('device')
iface_up_cmd = 'sudo ifconfig eth0 up'


def parse_payload_size(payload_size):
    """ Build a random ascii payload of given size """

    size_units = {
        "B": 2 ** 0,
        "KB": 2 ** 10,
        "MB": 2 ** 20
    }

    unit = payload_size[-2:] if payload_size[-2] in ascii_letters else payload_size[-1:]
    size = int(payload_size[:-len(unit)]) * size_units[unit.upper()]

    return size


def sync_clock():
    """ Sync system clock with NTP server """
    query_sync_cmds = [
        # 'timedatectl',
        'sudo ntpdate -q 169.254.250.244'
    ]
    sync_cmd = 'sudo ntpdate 169.254.250.244'
    iface_down_cmd = 'sudo ifconfig eth0 down'

    logger.info("Synchronizing system clocks ...")

    # Check clock offset before sync
    pre_sync_res = []
    for cmd in query_sync_cmds:
        pre_sync_res.append(
            subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.decode())

    # Force clock synchronization
    for _ in range(5):
        sync_res = subprocess.run(sync_cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if abs(float(sync_res.stdout.decode().strip().split(' ')[-2])) * 1000 < 10:
            break

    # Check clock offset after sync
    post_sync_res = []
    for cmd in query_sync_cmds:
        post_sync_res.append(
            subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.decode())

    # Shutdown network interface
    iface_down_res = subprocess.run(iface_down_cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    logger.info("System clocks synchronized")

    return [
        pre_sync_res,
        sync_res.stdout.decode(),
        post_sync_res,
        iface_down_res.returncode
    ]


def check_connectivity():
    """ Check network status """

    logger.info("Checking connectivity ...")

    for iface in ifcfg.interfaces().values():
        logger.info(f'Network interface: {iface["device"]}')
        logger.info(f'Ipv4 address: {iface["inet"]}')
        logger.info(f'Subnet mask: {iface["netmask"]}')
        logger.info(f'Broadcast address: {iface["broadcast"]}')

    subprocess.run('ping -c 3 -I usb0 8.8.8.8'.split())


def network_status(output_path):
    """ Save network status information on the given file """

    status = []
    if os.path.exists(output_path):
        with open(output_path, 'r') as fin:
            status = json.load(fin)

    outputs = send_commands(['AT+CNMP?', 'AT+CREG?', 'AT+CPSI?', 'AT+CSQ'])
    status.append(outputs)

    with open(output_path, 'w') as fout:
        json.dump(status, fout, indent=2)

    return status


def format_payload_size(size: str) -> str:
    size = size.strip().lower()
    if size.endswith("b") or size.endswith("kb") or size.endswith("mb") or size.endswith("gb"):
        return f"file-{size}"
    else:
        raise ValueError("Invalid size format. Use 'B', 'KB', 'MB', or 'GB'.")


def generate_ebpf_filename(config, timestamp=None):
    """Generate a descriptive filename for eBPF results based on configuration"""
    if timestamp is None:
        timestamp = time.strftime("%Y%m%d_%H%M%S")

    delay = f"{config['delay']}S"  # 0.4 -> 0_4S


    return f"ebpf_{config['experiment']}_{delay}_{config['radio_generation']}_{config['payload_size']}_{timestamp}"

def emit_gpio_marker():

    SYNC_PIN = 17  # GPIO17 (BCM numbering)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(SYNC_PIN, GPIO.OUT, initial=GPIO.LOW)

    time.sleep(0.05)  # Stabilize

    GPIO.output(SYNC_PIN, GPIO.HIGH)
    time.sleep(0.01)
    GPIO.output(SYNC_PIN, GPIO.LOW)

    return time.monotonic_ns()


