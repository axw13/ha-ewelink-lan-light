# eWeLink LAN Light

A Home Assistant custom integration for local control of compatible eWeLink RGB
bulbs, without a cloud account. Includes RGB, 2000–6500 K white, brightness,
on/off and an optional colour-before-power action. The tested hardware and
firmware are listed below; compatibility with other models is unverified.

## Tested model

These details were supplied by the operator from the tested bulb and its firmware
dump. They describe the test hardware; this repository does not contain the dump.

| Item | Value |
| --- | --- |
| Product | eWeLink Smart GU10 RGB+CCT bulb (RGB plus tunable white) |
| Wi-Fi module / board | BW2L |
| Chip | Bouffalo Lab BL602 (RISC-V, 2.4 GHz Wi-Fi) |
| Flash | 2 MiB (2,097,152-byte dump) |
| Crystal | 40 MHz, marked LK40 |
| Firmware | `FWLED-CK0205PWM-LIGHT-BL602L`, version **1.7.1** |
| Factory model string | `CK-BL602-5PWM-01` |
| PWM channels | Five: red, green, blue, cold white, warm white |
| Internal light type | `light_ck0205pwm` |
| LAN control | HTTP on TCP **8081** |
| State | Encrypted TXT record of mDNS service `_ewelink._tcp.local.` (UDP 5353): multicast announcements, plus a unicast query every 10 s |
| LAN encryption | AES-128-CBC with a key derived as MD5(device key) |

The five PWM channels describe the bulb hardware, not five separately exposed
HA entities. The integration exposes RGB and colour-temperature controls for
each bulb. The local pairing/provisioning test scope is documented in the
[credential guide](docs/device-credentials.md#what-was-actually-tested).

## Requirements

Home Assistant Core 2026.10.1 or later. This version uses Core's probatio-based
entity-service helper. Compatibility with future Core releases is not guaranteed.
The integration installs its declared pycryptodome dependency through HA.
HA must reach the bulb's LAN HTTP endpoint (TCP 8081) and UDP 5353 on the bulb. State is
polled every 10 s with a unicast mDNS query, so it also works across VLANs without an mDNS
repeater; multicast announcements, when they arrive, update it instantly. After 3 missed
polls the light shows as unavailable. The bulb's firmware version appears in its device info.

## Retrieve the bulb ID and key

Follow [Retrieve a bulb's device ID, key and LAN address](docs/device-credentials.md).
It covers AP pairing, `/device` with the `Package-Name` header, `deviceid`/`apikey`
mapping, and the tested local `/ap` provisioning request with a nonresolving
cloud endpoint. It also explains DHCP verification (request success does not
prove Wi-Fi joined), reservations and entering the values in HA. Existing
working entries do not need to be reset or paired again.
All credential examples are placeholders.

## Installation with HACS

1. Open **HACS → menu (three dots) → Custom repositories**.
2. Add `https://github.com/axw13/ha-ewelink-lan-light` with type **Integration**.
3. Find **eWeLink LAN Light** in HACS and download it. Back up an existing
   installation before replacing its files.
4. Run HA's configuration check and restart Core.
5. Open **Settings → Devices & services → Add integration → eWeLink LAN Light
   (no cloud)** and enter the bulb's normal LAN address, device ID and device key.

This is a custom repository, not a claim of inclusion in the default catalog.
See the [HACS custom-repository instructions](https://www.hacs.dev/docs/faq/custom_repositories/).
Compatibility with future Marketplace versions has not been tested.

## Manual installation

1. Download the source archive from a tagged release or clone this repository.
2. Back up the installed integration, then copy the entire
   `custom_components/ewelink_lan_light` directory into HA's
   `/config/custom_components/`. Do not copy personal configuration into this repo.
3. Run HA's configuration check, restart Core, then open **Settings → Devices &
   services → Add integration → eWeLink LAN Light (no cloud)**.
4. Enter the bulb address, device ID and device key locally in the HA form.
   The key field is masked. Existing entries keep their integration domain and
   unique IDs; do not remove/re-add them merely to update the source.

HA stores these credentials in its local config entry. They are not included in
this repository. Protect HA configuration backups accordingly.

## Colour before power

The optional `ewelink_lan_light.prepare_color` action sends only colour/brightness;
it never sends power-on. Provide exactly one of `rgb_color` (three channels,
0–255) or `color_temp_kelvin` (2000–6500), and `brightness_pct` (1–100).
Follow it with `light.turn_on` without colour or brightness parameters.
Select your own light entity in the HA automation editor for both actions.

A failed preparation stops the sequence by default. Existing combined turn-on
behavior remains unchanged. Some firmware ignores colour changes while off.
HA state can be optimistic until a push announcement arrives, so command
acknowledgment does not prove the bulb's physical startup appearance.

## Verification and updates

Run `python3 tests/test_order.py` for seven mocked transport regression checks.
They send no network requests and do not operate physical devices. Compile checks
and packaging/privacy review are also recommended before releases. These tests
do not replace a real HA configuration check and a controlled hardware test.
Back up before upgrading; retain this action while automations reference it.

Packaging references:
- https://www.hacs.dev/docs/publish/integration/
- https://contributors.home-assistant.io/marketplace/reference/repository-structure/
