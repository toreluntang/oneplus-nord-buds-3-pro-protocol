# OnePlus Nord Buds 3 Pro — control protocol

This project reverse-engineers the control protocol of the **OnePlus Nord Buds 3 Pro**, so they can be controlled without HeyMelody or a OnePlus phone. The planned clients are a macOS app and an Android (Pixel) app.

**Status:** macOS can talk to the buds over BLE GATT. These work:
- reading battery levels
- reading firmware versions
- reading and setting ANC mode
- reading and setting touch gestures

The ANC mode codes still need ground truth. See [PROTOCOL.md](PROTOCOL.md) for everything verified so far.

## Probe tools (macOS)

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# BLE GATT: dump the GATT table and send read-only queries (battery, ANC, touch, firmware)
.venv/bin/python probe/gatt_probe.py

# Send specific commands as CMD:PAYLOAD hex
.venv/bin/python probe/gatt_probe.py --cmd 010c:0101        # read ANC mode
.venv/bin/python probe/gatt_probe.py --cmd 010c:0201        # read long-press cycle mask

# Classic Bluetooth: list SDP records / RFCOMM channels
.venv/bin/python probe/sdp_dump.py xx-xx-xx-xx-xx-xx
```

The first query after connecting sometimes gets no reply. Re-run it if that happens.

Your terminal app needs Bluetooth permission (System Settings → Privacy & Security → Bluetooth).

## Credits

- [Gadgetbridge](https://codeberg.org/Freeyourgadget/Gadgetbridge): its OPPO/realme headphones implementation (`service/devices/oppo/`) documents the same protocol family.
- [cracked-oneplus-buds](https://github.com/AasheeshLikePanner/cracked-oneplus-buds): a macOS proof of concept for this model that showed the GATT transport.
