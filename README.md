# Power estimation via passive collection of network metrics based on eBPF approach.

This repository contains all components developed and used for the thesis project, including report files, data processing scripts, automation tools, validation scripts, and experimental payloads.

## Folder Overview

- **matlab_part/**  
  Contains MATLAB scripts for data processing, feature extraction, modeling, and result generation.  
  Includes a detailed README explaining how to run the scripts and reproduce the results.

- **otii_automation_part/**  
  Contains the Otii Automation tool developed for synchronized trace collection on both controller and device (tested on Raspberry Pi 400).  
  Includes its own README with installation and usage instructions.

- **packet_validation/**  
  Contains script used for validation runs comparing eBPF monitoring outputs (CSV counters) with tcpdump PCAP captures.  
  Used to verify the accuracy of the eBPF monitoring tool.

- **payloadshttp_server/**  
  Contains files generated for the HTTP experiment, served using Python’s built-in HTTP server during traffic generation.

- **ebpf_part/**  
  Contains the eBPF monitoring tool:  
  - Kernel-side program written in C  
  - User-space controller written in Python using the BCC framework
 
## Acknowledgements
Prof. Alessio Vecchio
Eng. Valerio Luconi

