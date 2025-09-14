# Otii Automation

## Overview

This project provides automation scripts for synchronized experiments involving power and network trace collection. The scripts are designed to run on both the controller and the device (tested on Raspberry Pi 400).

## Installation

### Device Setup (tested on raspberry Pi 400)

Install BCC Tools and eBPF Dependencies:

echo "deb http://cloudfront.debian.net/debian sid main" | sudo tee -a /etc/apt/sources.list
sudo apt-get update
sudo apt-get install -y bpfcc-tools libbpfcc libbpfcc-dev linux-headers-$(uname -r)

Set up Python environment and install dependencies:

python3 -m pip install -U pip
python3 -m venv <venv_path>
source <venv_path>/bin/activate
pip3 install -r requirements_device.txt

### Controller Setup

Set up Python environment and install dependencies (virtual environment is optional but recommended):

python3 -m pip install -U pip
python3 -m venv <venv_path>
source <venv_path>/bin/activate
pip3 install -r requirements_controller.txt

## Running Experiments

On the device (run with sudo due to eBPF access):

sudo /path/to/venv/bin/python main.py device

On the controller:

python3 main.py controller
