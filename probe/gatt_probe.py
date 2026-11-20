"""Connect to the buds over BLE GATT (CoreBluetooth), dump the GATT table, and send OPPO-protocol frames.

Frame: AA | len(=7+n) | 00 00 | cmd u16le | seq | n u16le | payload[n]   (responses: cmd | 0x8000)

Usage: gatt_probe.py [--cmd CMD:PAYLOADHEX ...] [--seconds N]
  default: read-only queries (battery, ANC state, touch config, firmware)
"""
import argparse
import itertools
import time

import CoreBluetooth as CB
import objc
from Foundation import NSDate, NSObject, NSRunLoop

SVC_079A = "0000079A-D102-11E1-9B23-00025B00A5A5"
WRITE_079A = "0100079A-D102-11E1-9B23-00025B00A5A5"

READ_ONLY = [
    ("battery", 0x0106, b""),
    ("anc?", 0x010C, bytes([0x01, 0x01])),
    ("touch?", 0x0108, bytes([0x02, 0x03, 0x01])),
    ("firmware?", 0x0105, b""),
]

_seq = itertools.count(0x10)


def frame(cmd: int, payload: bytes) -> bytes:
    n = len(payload)
    return bytes([0xAA, 7 + n, 0, 0, cmd & 0xFF, cmd >> 8, next(_seq) & 0xFF, n & 0xFF, n >> 8]) + payload


def describe(buf: bytes) -> str:
    if len(buf) < 9 or buf[0] != 0xAA:
        return ""
    i = 1  # length is LEB128 (1+ bytes)
    while buf[i] & 0x80:
        i += 1
    i += 1 + 2  # skip last length byte + 00 00
    cmd = buf[i] | buf[i + 1] << 8
    seq = buf[i + 2]
    n = buf[i + 3] | buf[i + 4] << 8
    body = buf[i + 5:i + 5 + n]
    shown = body.hex(" ") if n <= 48 else f"{body[:24].hex(' ')} … (+{n - 24} bytes)"
    return f"cmd=0x{cmd:04x} seq=0x{seq:02x} payload[{n}]={shown}"


def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.05))


class Probe(NSObject):
    def init(self):
        self = objc.super(Probe, self).init()
        self.periph = None
        self.write_char = None
        self.pending = 0
        self.ready = False
        return self

    def centralManagerDidUpdateState_(self, cm):
        print(f"central state={cm.state()}", flush=True)
        if cm.state() != CB.CBManagerStatePoweredOn:
            return
        found = cm.retrieveConnectedPeripheralsWithServices_([CB.CBUUID.UUIDWithString_(SVC_079A)])
        print(f"connected peripherals with 079A service: {[p.name() for p in found]}", flush=True)
        if found:
            self.periph = found[0]
            self.periph.setDelegate_(self)
            cm.connectPeripheral_options_(self.periph, None)

    def centralManager_didConnectPeripheral_(self, cm, p):
        print(f"GATT connected: {p.name()} {p.identifier().UUIDString()}", flush=True)
        p.discoverServices_(None)

    def centralManager_didFailToConnectPeripheral_error_(self, cm, p, err):
        print(f"connect failed: {err}", flush=True)

    def peripheral_didDiscoverServices_(self, p, err):
        services = p.services() or []
        self.pending = len(services)
        for s in services:
            p.discoverCharacteristics_forService_(None, s)

    def peripheral_didDiscoverCharacteristicsForService_error_(self, p, s, err):
        print(f"service {s.UUID().UUIDString()}", flush=True)
        for c in s.characteristics() or []:
            props = c.properties()
            flags = [n for n, b in (("read", 0x02), ("wnr", 0x04), ("write", 0x08), ("notify", 0x10), ("indicate", 0x20)) if props & b]
            print(f"    char {c.UUID().UUIDString()}  {','.join(flags)}", flush=True)
            if props & 0x30:
                p.setNotifyValue_forCharacteristic_(True, c)
            if c.UUID().UUIDString() == WRITE_079A:
                self.write_char = c
        self.pending -= 1
        if self.pending == 0:
            self.ready = True

    def peripheral_didUpdateValueForCharacteristic_error_(self, p, c, err):
        buf = bytes(c.value() or b"")
        print(f"{time.strftime('%H:%M:%S')} <- {c.UUID().UUIDString()[:8]} {buf.hex(' ')}   {describe(buf)}", flush=True)

    @objc.python_method
    def send(self, data: bytes):
        print(f"{time.strftime('%H:%M:%S')} -> {data.hex(' ')}   {describe(data)}", flush=True)
        self.periph.writeValue_forCharacteristic_type_(data, self.write_char, CB.CBCharacteristicWriteWithoutResponse)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", nargs="*", help="CMD:PAYLOADHEX, e.g. 010c:0101")
    ap.add_argument("--seconds", type=float, default=4)
    ap.add_argument("--gap", type=float, default=1.2, help="seconds between commands")
    args = ap.parse_args()
    cmds = READ_ONLY if not args.cmd else [
        (c, int(c.split(":")[0], 16), bytes.fromhex(c.split(":")[1] if ":" in c else "")) for c in args.cmd]

    probe = Probe.alloc().init()
    cm = CB.CBCentralManager.alloc().initWithDelegate_queue_(probe, None)  # noqa: F841 (keep alive)
    end = time.time() + 15
    while not probe.ready and time.time() < end:
        pump(0.2)
    if not probe.ready or probe.write_char is None:
        print(f"not ready (ready={probe.ready}, write_char={probe.write_char is not None})")
        return
    pump(1.5)  # let notification subscriptions settle
    for label, cmd, payload in cmds:
        print(f"--- {label}")
        probe.send(frame(cmd, payload))
        pump(args.gap)
    pump(args.seconds)


if __name__ == "__main__":
    main()
