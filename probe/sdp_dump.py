"""Dump classic Bluetooth SDP service records (incl. RFCOMM channels) for a paired device."""
import os
import sys
import time

import IOBluetooth
from Foundation import NSDate, NSRunLoop

ADDR = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BUDS_ADDR", "")
if not ADDR:
    sys.exit("usage: sdp_dump.py <bt-address>  (or set BUDS_ADDR; find it with: system_profiler SPBluetoothDataType)")

dev = IOBluetooth.IOBluetoothDevice.deviceWithAddressString_(ADDR)
if dev is None:
    sys.exit(f"device {ADDR} not found")
print(f"{dev.name()}  connected={dev.isConnected()}")

# Ask for a fresh SDP query, then pump the run loop while it completes.
dev.performSDPQuery_(None)
deadline = time.time() + 10
while time.time() < deadline:
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.25))

for rec in dev.services() or []:
    name = rec.getServiceName()
    ok, ch = rec.getRFCOMMChannelID_(None)
    ok_psm, psm = rec.getL2CAPPSM_(None)
    uuids = []
    cls = rec.getAttributeDataElement_(0x0001)  # ServiceClassIDList
    if cls is not None:
        for el in cls.getArrayValue() or []:
            uuids.append(str(el.getUUIDValue()))
    print(f"- {name!s:40} rfcomm={ch if ok == 0 else '-':>3}  "
          f"psm={psm if ok_psm == 0 else '-':>5}  class={uuids}")
