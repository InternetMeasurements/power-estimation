#!/usr/bin/python3

import sys
from bcc import BPF
import pyroute2
import csv
import subprocess
import time
import signal

def usage():
    print("Usage: {0} <ifdev>".format(sys.argv[0]))
    sys.exit(1)

if len(sys.argv) != 2:
    usage()

device = sys.argv[1]

# Load and attach eBPF program
bpf = BPF(src_file="data_logger.c")
fn_ingress = bpf.load_func("handle_ingress", BPF.XDP)
bpf.attach_xdp(device, fn_ingress)

ipr = pyroute2.IPRoute()
ipdb = pyroute2.IPDB(nl=ipr)
idx = ipdb.interfaces[device].index
ipr.tc("add", "clsact", idx)
fn_egress = bpf.load_func("handle_egress", BPF.SCHED_CLS)
ipr.tc("add-filter", "bpf", idx, ":1", fd=fn_egress.fd, name=fn_egress.name,
       parent="ffff:fff3", classid=1, direct_action=True)

print(f"[INFO] eBPF program attached to {device}")

# Open CSV
with open("packet_data.csv", "w") as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerow(["Timestamp (ns)", "IAT (ns)", "Packet Length", "Direction"])

    # Callback function for perf buffer (no print)
    def process_event(cpu, data, size):
        event = bpf["events"].event(data)
        direction = "Incoming" if event.direction == 0 else "Outgoing"
        csv_writer.writerow([event.timestamp_ns, event.iat_ns, event.packet_length, direction])

    bpf["events"].open_perf_buffer(process_event)

    # Start tcpdump in background
    tcpdump_proc = subprocess.Popen(
        ["sudo", "tcpdump", "-i", device, "-tt", "-nn", "-w", "capture.pcap"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # Start your traffic generation script (background curl with random sleep)
    traffic_cmd = """
echo "Starting 60-second traffic simulation..."
for i in {1..60}; do
    curl -s -o /dev/null https://www.google.com/ &
    sleep $(awk -v min=0.05 -v max=1 'BEGIN{srand(); print min+rand()*(max-min)}')
done
"""
    traffic_proc = subprocess.Popen(["bash", "-c", traffic_cmd])

    print("[INFO] tcpdump and traffic generation started.")

    try:
        start = time.time()
        while time.time() - start < 65:  # Wait slightly longer to ensure all requests finish
            bpf.perf_buffer_poll(timeout=100)
    except KeyboardInterrupt:
        print("[INFO] Interrupted by user.")
    finally:
        print("[INFO] Cleaning up...")
        bpf.remove_xdp(device)
        ipr.tc("del", "clsact", idx)
        ipdb.release()
        tcpdump_proc.send_signal(signal.SIGINT)
        traffic_proc.terminate()
        print("[INFO] Done.")
