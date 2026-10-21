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
| State announcements | mDNS service `_ewelink._tcp.local.`; mDNS transport uses UDP 5353 |
| LAN encryption | AES-128-CBC with a key derived as MD5(device key) |

The five PWM channels describe the bulb hardware, not five separately exposed
HA entities. The integration exposes RGB and colour-temperature controls for
each bulb. The local pairing/provisioning test scope is documented in the
[credential guide](docs/device-credentials.md#what-was-actually-tested).

## Requirements

Home Assistant Core 2026.10.1 or later. This version uses Core's probatio-based
entity-service helper. Compatibility with future Core releases is not guaranteed.
The integration installs its declared pycryptodome dependency through HA.
HA must reach the bulb's LAN HTTP endpoint and receive its mDNS announcements.

## Retrieve the bulb ID and key

Follow [Retrieve a bulb's device ID, key and LAN address](docs/device-credentials.md).
It covers AP pairing, `/device` with the `Package-Name` header, `deviceid`/`apikey`
mapping, and the tested local `/ap` provisioning request with a nonresolving
cloud endpoint. It also explains DHCP verification (request success does not
prove Wi-Fi joined), reservations and entering the values in HA. Existing
working entries do not need to be reset or paired again.
All credential examples are placeholders.

## Installation from this private repository

HACS and the Home Assistant Marketplace only consume public repositories. This
repository is deliberately private; adding its URL there will not install it.
The directory layout and metadata follow their integration packaging convention,
so the same files can be used there if visibility is explicitly changed later.
Do not change visibility without a fresh security review and owner approval.

1. Download the source archive from a tagged release while signed into GitHub,
   or clone this repository using your own authenticated GitHub session.
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

## Privacy

This repository contains integration source, synthetic unit tests and generic
documentation only. It contains no personal automation/dashboard exports, HA
storage files, live device IDs/keys, passwords, access tokens or network inventory.
Do not upload logs or diagnostics without reviewing and redacting them first.

Packaging references:
- https://www.hacs.dev/docs/publish/integration/
- https://contributors.home-assistant.io/marketplace/reference/repository-structure/
