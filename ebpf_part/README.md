# power-estimation

Power estimation via passive collection of network metrics based on eBPF approach.

## Usage
To install BCC toolchain and bpf libraries(this is on debian):

```bash
echo "deb http://cloudfront.debian.net/debian sid main" | sudo tee -a /etc/apt/sources.list
sudo apt-get update
sudo apt-get install -y bpfcc-tools libbpfcc libbpfcc-dev linux-headers-$(uname -r)
```
To run the ebpf part:

```bash
sudo python3 monitoring_tool.py <ifdev>
```
where ifdev is the network interface name
