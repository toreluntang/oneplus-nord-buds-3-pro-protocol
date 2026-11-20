# OnePlus Nord Buds 3 Pro — control protocol notes

These notes were verified against real buds (firmware 1.5.5, BES chipset) from macOS on 2026-11-20 using `probe/gatt_probe.py`.
The protocol is the OPPO/realme "HeyMelody" family that Gadgetbridge implements (`service/devices/oppo/`).

## Transport

**BLE GATT works.** It was confirmed from macOS CoreBluetooth while the buds were also connected over classic Bluetooth for audio, and it needed no handshake or registration.

| Role | UUID | Properties |
|---|---|---|
| Service | `0000079A-D102-11E1-9B23-00025B00A5A5` | |
| Write (TX) | `0100079A-D102-11E1-9B23-00025B00A5A5` | write without response |
| Notify (RX) | `0200079A-D102-11E1-9B23-00025B00A5A5` | notify; subscribe before sending |

macOS finds the peripheral with `retrieveConnectedPeripheralsWithServices([079A])`. No scan is needed because the buds are already connected.

The buds have other GATT services that this protocol doesn't need:
- `FE2C` (Google Fast Pair)
- `66666666-…` (BES OTA)
- `0000079C-…` (notify-only)

Classic RFCOMM channels, from SDP:
- channel 12, UUID `0000079a-…`: the same protocol. On macOS the RFCOMM open never completed, so use GATT.
- channel 13: BESOTA (firmware updates)
- channel 17: Google Fast Pair message stream. Opening it works. It pushes the model ID `0x402292` and battery levels.
- channel 29: "WATCH" (unknown)

On Android (Pixel), Gadgetbridge connects over RFCOMM by SDP UUID `0000079a-…`. Either route should work.

## Frame format

```
AA | len (LEB128) | 00 00 | cmd (u16 LE) | seq | n (u16 LE) | payload[n]
len = 7 + n
```

- There is no checksum.
- A response uses `cmd | 0x8000`, echoes the request's `seq`, and its first payload byte is a status (`00` = OK).
- Unsolicited frames from the buds use their own `seq` counter.
- Long frames use 2-byte LEB128 lengths, for example `aa b6 01` means 182.

## Commands (verified)

| Purpose | cmd | Request payload | Response payload |
|---|---|---|---|
| Battery | `0x0106` | — | `00, count, (idx, level)…`. idx 1 = left, 2 = right, 3 = case; level bit `0x80` = charging. |
| Firmware | `0x0105` | — | `00, count, ASCII "comp,field,value,…"` |
| ANC get | `0x010C` | `01 01` | `00 01 01 <state>` |
| ANC set | `0x0404` | `01 01 <mode>` | `00` |
| Touch get | `0x0108` | `02 03 01` | `00, count, (side, 01, gesture, action)…` |
| Touch set | `0x0401` | `01, side, 01, gesture, action` | `00` |

### ANC / noise control

The request and set payloads follow Gadgetbridge's `AncConfigModule`:
- Get: `0x010C` with payload `<type> 01`
- Set: `0x0404` with payload `<type> 01 <value>`
- Reply: `00 <type> 01 <value>`

| type | Meaning | Value read on these buds |
|---|---|---|
| `01` | current mode | `01`, `04` or `10` (see below) |
| `02` | modes the long-press cycles through (bitmask, at least 2 modes) | `07` (three modes) |
| `04` | dynamic ANC level | `40` |

Every set was acknowledged with status `00`. These are the mode values set and the state the buds then reported:

| Value set | State reported | Notes |
|---|---|---|
| `01` | `01` | Confirmed **off** by ear, twice. |
| `02` | `10` | |
| `04` | `04` | User was "pretty sure" this state was transparency, after a long-press. |
| `08` | `04` | |

**Current hypothesis, still unconfirmed:** for setting, `01` = off, `02` = ANC and `04` = transparency, which fits the cycle bitmask `07` = `01|02|04`. Under that reading, the reported `10` and `04` may be Gadgetbridge's "ANC level" codes (normal `10`, low `04`), not mode codes.

The two public sources disagree with these results:
- Gadgetbridge (OPPO/realme): off `01`, transparency `02`, on `08`
- The Nord Buds 3 Pro Swift tool: on `01`, transparency `02`, off `04`

**Next step:** get ground truth by capturing the official app's traffic with an Android HCI snoop log, using the old phone (a OnePlus).

Other observations:
- When the mode changes, the buds also send an unsolicited `0x0204` frame with payload `03 01 01 <state>`.
- Once, setting `01` right after an ANC mode reported `10` and stayed there. Every other time, `01` reported `01`.

**Idea for "ANC can't turn on by accident":** set the cycle mask (type `02`) to off + transparency only, which is `05` under the hypothesis above. This hasn't been applied yet.

### Touch controls

- **Side:** `01` = left, `02` = right.
- **Gesture byte**, sent after `01`:
  - `01` single tap
  - `02` double tap
  - `03` triple tap
  - `04` long press
  - `06` unknown (maybe press-and-hold on both buds)
- **Action**, from Gadgetbridge:
  - `00` none
  - `01` play/pause
  - `03` voice assistant (`04` on realme)
  - `05` previous
  - `06` next
  - `08` noise control
  - `0B` volume up
  - `0C` volume down
  - `11` game mode
- **Not yet verified on this model:** actions other than 00, 01, 05, 06 and 08.

Default config read from the buds:

| Gesture | Left | Right |
|---|---|---|
| single tap | 01 play/pause | 00 none |
| double tap | 06 next | 06 next |
| triple tap | 05 previous | 05 previous |
| long press | 08 noise control | 08 noise control |
| `06` | 00 | 00 |

A test write (right single tap set to `01`, then back to `00`) was acknowledged and read back correctly.

## Unsolicited frames seen

- `0x0204`: status push. The first payload byte is the type:
  - `01` battery
  - `02` unknown
  - `03` ANC
  - `07` a JSON diagnostics blob (`sco_caton`, link-quality counters)
- `0x0400`: the multipoint paired-device list (device names as null-terminated strings).
- `0x0500`: unknown, payload `00 00 00 00`.

## Open questions

- Confirm the ANC mode codes with an HCI snoop log of the official app.
- The meaning of the ANC levels: dynamic level reads `40`.
- The full action list for this model, and what gesture `06` is.
- EQ, which isn't explored yet.
