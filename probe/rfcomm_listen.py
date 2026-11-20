"""Open an RFCOMM channel to the buds, optionally send hex frames, and hex-dump everything received.

Usage: BUDS_ADDR=xx-xx-xx-xx-xx-xx rfcomm_listen.py [--channel 12] [--seconds 10] [--send HEX ...]
"""
import argparse
import os
import time

import IOBluetooth
import objc
from Foundation import NSDate, NSObject, NSRunLoop

ADDR = os.environ.get("BUDS_ADDR", "")  # classic BT address, e.g. "xx-xx-xx-xx-xx-xx"


class Delegate(NSObject):
    def rfcommChannelData_data_length_(self, channel, data, length):
        buf = bytes(data[:length]) if not isinstance(data, bytes) else data[:length]
        print(f"{time.strftime('%H:%M:%S')} <- [{length:3}] {buf.hex(' ')}", flush=True)

    def rfcommChannelOpenComplete_status_(self, channel, status):
        print(f"open complete status={status}", flush=True)

    def rfcommChannelClosed_(self, channel):
        print("channel closed", flush=True)


def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", type=int, default=12)
    ap.add_argument("--seconds", type=float, default=10)
    ap.add_argument("--send", nargs="*", default=[])
    args = ap.parse_args()

    dev = IOBluetooth.IOBluetoothDevice.deviceWithAddressString_(ADDR)
    delegate = Delegate.alloc().init()
    status, chan = dev.openRFCOMMChannelSync_withChannelID_delegate_(None, args.channel, delegate)
    print(f"openRFCOMMChannelSync status={status} mtu={chan.getMTU() if chan else None}", flush=True)
    pump(1)
    print(f"isOpen={chan.isOpen() if chan else None}", flush=True)
    if not chan or not chan.isOpen():
        return
    for frame in args.send:
        payload = bytes.fromhex(frame)
        print(f"{time.strftime('%H:%M:%S')} -> [{len(payload):3}] {payload.hex(' ')}", flush=True)
        chan.writeSync_length_(payload, len(payload))
        pump(1.5)
    pump(args.seconds)
    chan.closeChannel()


if __name__ == "__main__":
    main()
