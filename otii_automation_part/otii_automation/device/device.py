import threading
import traceback
import logging
import os
import json
import time
import subprocess
from threading import Thread
from bcc import BPF
import pyroute2
import csv
from .protocols.http_client import fetch_payload
from .util import logger, parse_payload_size, iface_up_cmd, \
    format_payload_size, generate_ebpf_filename, emit_gpio_marker
from .at_command import reset_nic
from .protocols.mqtt import aoi_rawmqtt
from ..rdt import Rdt
from ..rdt.exception import RdtException
from ..rdt.message import Message
from ..rdt.udt.uart_serial import UdtUartSerial

rdt = Rdt(UdtUartSerial('/dev/ttyS0'))

server_config = None


def start_ebpf(device, output_file, stop_event, result_dir, ready_event):
    """Start the eBPF program and log metrics to a CSV file."""
    # Get the directory where this script is located
    logger.info(f"THREAD HAS STARTED")

    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Construct the correct path to the eBPF file
    ebpf_path = os.path.join(script_dir, "ebpf", "data_logger.c")

    # Verify the file exists
    if not os.path.exists(ebpf_path):
        raise FileNotFoundError(f"eBPF source file not found at: {ebpf_path}")
    markers = []  # List to store timestamp events

    # Load the BPF program
    bpf = BPF(src_file=ebpf_path)
    fn_ingress = bpf.load_func("handle_ingress", BPF.XDP)
    bpf.attach_xdp(device, fn_ingress)

    ipr = pyroute2.IPRoute()
    ipdb = pyroute2.IPDB(nl=ipr)
    idx = ipdb.interfaces[device].index
    ipr.tc("add", "clsact", idx)
    fn_egress = bpf.load_func("handle_egress", BPF.SCHED_CLS)
    ipr.tc("add-filter", "bpf", idx, ":1", fd=fn_egress.fd, name=fn_egress.name,
           parent="ffff:fff3", classid=1, direct_action=True)

    # Now everything is attached,Emit sync pulse
    marker_start = emit_gpio_marker()
    markers.append({'event': 'start_ebpf', 'timestamp_ns': marker_start})

    # Signal the main thread that eBPF is ready
    ready_event.set()

    try:
        with open(output_file, "w") as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(["Timestamp (ns)", "IAT (ns)", "Packet Length", "Direction"])

            def process_event(cpu, data, size):
                event = bpf["events"].event(data)
                direction = "Incoming" if event.direction == 0 else "Outgoing"
                csv_writer.writerow([event.timestamp_ns, event.iat_ns, event.packet_length, direction])

            bpf["events"].open_perf_buffer(process_event)

            # Main polling loop with stop condition
            while not stop_event.is_set():
                bpf.perf_buffer_poll(timeout=100)  # 100ms timeout to check stop_event

    finally:
        marker_end = emit_gpio_marker()
        markers.append({'event': 'end_ebpf', 'timestamp_ns': marker_end})

        # Save marker timestamps to file
        with open(os.path.join(result_dir, 'markers.json'), 'w') as f:
            json.dump(markers, f, indent=2)

        logger.info("Cleaning up eBPF resources...")
        # Cleanup operations
        bpf.remove_xdp(device)
        ipr.tc("del", "clsact", idx)
        ipdb.release()
        logger.info("eBPF program stopped cleanly")


def start_configuration(config):
    global server_config

    timestamps = {'launch': int(time.time_ns())}
    os.makedirs("results", exist_ok=True)

    logger.info(f'Start configuration {config}')
    timestamps['network_info'] = int(time.time_ns())

    # Generate unique results directory for this run
    run_timestamp = time.strftime("%Y%m%d_%H%M%S")
    ebpf_base_name = generate_ebpf_filename(config, run_timestamp)
    config['results_dir'] = os.path.join("results", ebpf_base_name)
    os.makedirs(config['results_dir'], exist_ok=True)

    payload_size = parse_payload_size(config['payload_size'])

    rdt.send(Message.START_REQ)

    if config['experiment'] == 'http':
        payload_file_name = format_payload_size(config['payload_size'])
        experiment_duration = 60
        request_count = 0

        # Generate descriptive filename
        ebpf_csv = os.path.join(config['results_dir'], "ebpf_trace.csv")

        # Create an Event to signal that eBPF is fully attached
        ebpf_ready_event = threading.Event()

        # Create stop event for eBPF thread
        stop_event = threading.Event()
        device = "wlan0"
        ebpf_thread = Thread(target=start_ebpf, args=(device, ebpf_csv, stop_event, config['results_dir'], ebpf_ready_event))
        ebpf_thread.start()

        # Wait for eBPF to finish setup before starting experiment
        logger.info("Waiting for eBPF thread to finish setup...")
        ebpf_ready_event.wait()

        logger.info("eBPF program is active, beginning HTTP traffic...")
        logger.info(f"Starting HTTP experiment with eBPF for {experiment_duration} seconds.")
        start_time = time.time()

        try:
            while time.time() - start_time < experiment_duration:
                timestamps['start_req'], timestamps['stop_req'], status_code = fetch_payload(
                    config['host'], config['port'], payload_file_name
                )
                request_count += 1
                if status_code != 0:
                    raise Exception(f"Failed to fetch {payload_file_name} - Status code: {status_code}")
                time.sleep(config['delay'])
        except Exception as e:
            logger.error(f"Error during HTTP experiment: {e}")
        finally:
            # Gracefully stop eBPF thread
            stop_event.set()
            ebpf_thread.join()
            logger.info("HTTP experiment and eBPF tracking completed.")

        req_result = None
    else:
        req_result = aoi_rawmqtt(
            config['host'], config['port'], config['transport_protocol'], config['qos'],
            config['topic'], payload_size, config['rate'], config['duration'], config['queue']
        )

    rdt.send(Message.STOP_REQ)

    with open(os.path.join(config['results_dir'], 'timestamps.json'), 'w') as fout:
        json.dump(timestamps, fout, indent=2)

    # Wait for idle network card
    if config['experiment'] != 'aoi':
        time.sleep(25)

    rdt.send(Message.STOP_CONFIG)
    logger.info("Configuration completed")


def device():
    logging.getLogger('paramiko.transport').setLevel(logging.WARNING)

    while True:
        try:
            logger.info("Waiting for UART messages...")
            message, _ = rdt.receive()

            if message['code'] == Message.START_CONFIG.value:
                start_configuration(message['payload'])
            elif message['code'] == Message.END_EXPERIMENT.value:
                logger.info('Experiment concluded')
                break
            else:
                raise RdtException(f'Unknown command: {message}')
        except Exception as ex:
            logger.error(f'Exception on device: {ex}')
            logger.error(traceback.format_exc())

            # Activate Ethernet interface
            subprocess.run(iface_up_cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

            # Reset NIC, if not a RdtException
            if not isinstance(ex, RdtException):
                reset_nic()

            # Send error message
            try:
                rdt.send(Message.ERROR)
            except Exception as ex:
                logger.warning(f'Error message not sent: {ex}')
