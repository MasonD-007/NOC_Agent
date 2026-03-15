#!/bin/bash
# Auto-start iperf3 server on boot for edge-sw-02

apk add --no-cache iperf3

# Start iperf3 server in background
iperf3 -s -D

echo "iperf3 server started"
