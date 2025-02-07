#include <uapi/linux/bpf.h>
#include <linux/ip.h>
#include <linux/if_packet.h>
#include <uapi/linux/if_ether.h>
#include <uapi/linux/pkt_cls.h>

// Define a perf event map for streaming data to userspace
struct packet_event {
    u64 timestamp_ns;  // Current timestamp
    u64 iat_ns;        // Inter-arrival time
    u64 packet_length; // Packet length
    u8 direction;      // 0 = Incoming, 1 = Outgoing
};
BPF_PERF_OUTPUT(events);

// Define a map to store the last timestamp per CPU (for inter-arrival time)
BPF_PERCPU_ARRAY(last_timestamp, u64, 2); // Index 0: Incoming, 1: Outgoing

// Helper function to calculate inter-arrival time and stream data
static __always_inline void record_packet_event(void *ctx,u32 direction, u64 packet_length) {
    u64 now = bpf_ktime_get_ns(); // Current time in nanoseconds

    // Lookup last timestamp for the given direction
    u64 *last_time = last_timestamp.lookup(&direction);
    u64 iat = 0;
      if (last_time) {
        if (*last_time != 0) {
            iat = now - *last_time; // Calculate inter-arrival time if it's not the first packet
        }
    }
    last_timestamp.update(&direction, &now); // Update the last timestamp

    // Prepare event data
    struct packet_event event = {};
    event.timestamp_ns = now;
    event.iat_ns = iat;
    event.packet_length = packet_length;
    event.direction = direction;

    // Send the event to userspace via the perf buffer
    events.perf_submit(ctx, &event, sizeof(event));
}

// XDP Program for Incoming Packets
int handle_ingress(struct xdp_md *ctx) {
    // Packet length
    u64 len = (u64)(ctx->data_end - ctx->data);

    // Record event for incoming packets (direction = 0)
    record_packet_event(ctx,0, len);

    return XDP_PASS; // Let the packet pass
}

// TC Program for Outgoing Packets
int handle_egress(struct __sk_buff *skb) {
    // Packet length
    u64 len = skb->len;

    // Record event for outgoing packets (direction = 1)
    record_packet_event(skb,1, len);

    return TC_ACT_OK; // Let the packet pass
}
