#!/usr/bin/python

import sys
from bcc import BPF
from time import sleep
import pyroute2
import csv

def usage():
    print("Usage: {0} <ifdev>".format(sys.argv[0]))
    print("e.g.: {0} eth0\n".format(sys.argv[0]))
    exit(1)
if len(sys.argv) !=2:
    usage()

# Load the eBPF program
bpf = BPF(src_file="data_logger.c")

# Attach XDP program to a network interface for ingress traffic
device = sys.argv[1]
fn_ingress = bpf.load_func("handle_ingress", BPF.XDP)
bpf.attach_xdp(device, fn_ingress)

# Attach TC program to the same network interface for egress traffic
ipr = pyroute2.IPRoute()
ipdb = pyroute2.IPDB(nl=ipr)
idx = ipdb.interfaces[device].index
ipr.tc("add", "clsact", idx)
fn_egress = bpf.load_func("handle_egress", BPF.SCHED_CLS)
ipr.tc("add-filter", "bpf", idx, ":1", fd=fn_egress.fd, name=fn_egress.name,
       parent="ffff:fff3", classid=1, direct_action=True)

print(f"eBPF program attached to {device}. Press Ctrl+C to stop.")

# Open a CSV file for logging packet data
with open("packet_data.csv", "w") as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerow(["Timestamp (ns)", "IAT (ns)", "Packet Length", "Direction"])

    # Callback function to process events from the perf buffer
    def process_event(cpu, data, size):
        event = bpf["events"].event(data)
        direction = "Incoming" if event.direction == 0 else "Outgoing"
        csv_writer.writerow([event.timestamp_ns, event.iat_ns, event.packet_length, direction])
        print(f"{direction} Packet - Length: {event.packet_length} bytes, IAT: {event.iat_ns} ns")

    # Attach the perf buffer
    bpf["events"].open_perf_buffer(process_event)

    try:
        while True:
            bpf.perf_buffer_poll()
    except KeyboardInterrupt:
        # Clean up on exit
        print("Detaching program and exiting...")
        bpf.remove_xdp(device)
        ipr.tc("del", "clsact", idx)
        ipdb.release()
