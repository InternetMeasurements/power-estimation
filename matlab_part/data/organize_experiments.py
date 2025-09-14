import os
import re
import shutil

# --- Configuration ---
raw_data_dir = "raw"
energy_traces_dir = f"{raw_data_dir}/energy_traces"
ebpf_traces_dir = f"{raw_data_dir}/ebpf_traces"
output_dir = "grouped_experiments"

# --- Extract Parameters ---
def extract_parameters(name):
    try:
        interval = re.search(r"(\d+\.?\d*S)", name).group(1)
        size_match = re.search(r"(\d+(?:[KMG]?B))", name, re.IGNORECASE)
        if not size_match:
            raise ValueError(f"Size not found in: {name}")
        size = size_match.group(1).upper()
        network_match = re.search(r"(WIFI|LTE|ETH)", name, re.IGNORECASE)
        if not network_match:
            raise ValueError(f"Network type not found in: {name}")
        network = network_match.group(1).upper()
        return (interval, size, network)
    except Exception as e:
        print(f"Error parsing '{name}': {e}")
        return None

# --- Group Files ---
energy_groups = {}
ebpf_groups = {}

# Populate energy_groups from folders inside energy_traces_dir
for folder in os.listdir(energy_traces_dir):
    params = extract_parameters(folder)
    if params:
        energy_groups[params] = folder

# Populate ebpf_groups from subfolders that contain ebpf_trace.csv
for folder in os.listdir(ebpf_traces_dir):
    folder_path = os.path.join(ebpf_traces_dir, folder)
    if os.path.isdir(folder_path):
        params = extract_parameters(folder)
        if params:
            ebpf_csv_path = os.path.join(folder_path, "ebpf_trace.csv")
            if os.path.exists(ebpf_csv_path):
                ebpf_groups[params] = folder_path  # Store the folder path now
            else:
                print(f"Warning: ebpf_trace.csv not found in {folder_path}")

# --- Organize Files ---
os.makedirs(output_dir, exist_ok=True)

for params in energy_groups:
    if params in ebpf_groups:
        interval, size, network = params
        group_name = f"{interval}_{size}_{network}"
        group_dir = os.path.join(output_dir, group_name)
        os.makedirs(group_dir, exist_ok=True)

        # === Copy Main power file ===
        otii_folder = os.path.join(energy_traces_dir, energy_groups[params])
        src_power_csv = os.path.join(otii_folder, "Main power - Ace.csv")
        dst_power_csv = os.path.join(group_dir, "power_trace.csv")

        if os.path.exists(src_power_csv):
            shutil.copy(src_power_csv, dst_power_csv)
        else:
            print(f"Warning: 'Main power - Ace.csv' not found in {otii_folder}")

        # === Copy GPI trace if available ===
        src_gpi_csv = os.path.join(otii_folder, "GPI 1 - Ace.csv")
        dst_gpi_csv = os.path.join(group_dir, "gpi_trace.csv")

        if os.path.exists(src_gpi_csv):
            shutil.copy(src_gpi_csv, dst_gpi_csv)
        else:
            print(f"Note: 'GPI 1 - Ace.csv' not found in {otii_folder}")

        # === Copy eBPF trace ===
        src_ebpf = os.path.join(ebpf_groups[params], "ebpf_trace.csv")
        dst_ebpf = os.path.join(group_dir, "ebpf_trace.csv")
        shutil.copy(src_ebpf, dst_ebpf)

        # === Copy markers.json if available ===
        src_markers = os.path.join(ebpf_groups[params], "markers.json")
        dst_markers = os.path.join(group_dir, "markers.json")
        if os.path.exists(src_markers):
            shutil.copy(src_markers, dst_markers)
        else:
            print(f"Note: markers.json not found for {group_name}")

        print(f"Organized: {group_name}")
    else:
        print(f"Warning: No eBPF match for Otii experiment {params}")

print(f"Done! Organized data saved to: {output_dir}")
