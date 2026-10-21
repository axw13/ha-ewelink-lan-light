# Retrieve a bulb's device ID, key and LAN address

The integration needs three different values:

| HA field | Where it comes from |
| --- | --- |
| IP address | The bulb's normal address on your home Wi-Fi, from the router's DHCP leases |
| Device ID | The `deviceid` field returned by the bulb's pairing endpoint |
| Device key (apikey) | The pairing endpoint's `apikey` field; enter this as `devicekey` in HA |

The device key is separate from your Wi-Fi password, eWeLink account password,
HA access token and the protocol's fixed `selfApikey` value. None of those
substitutes for it. Each bulb has its own credentials.

LAN commands are AES-encrypted using a key derived from the device key. The
pairing API exposes the ID and key locally on the tested firmware; retrieving
them does not require a cloud login or capturing network traffic.

## Existing working bulbs

An existing HA entry already has the ID and key. Updating this integration does
not require collecting them again. Reuse an existing securely stored record if
you need to configure another HA installation. Do not reset a working bulb just
to follow this guide: pairing can disrupt control and may change credentials.

## Local pairing-access-point method

This is the local `/device` method referenced by this integration's setup code.
It applies only to firmware that exposes that endpoint in compatible/AP pairing
mode. Other eWeLink, Tuya, LEDVANCE or Matter products may use different methods.

1. Work on one bulb at a time. Put it in compatible/AP pairing mode so it
   broadcasts its own Wi-Fi instead of joining the home network. A previously
   configured bulb may need a reset. **The exact reset sequence and the setup
   SSID observed on this model were not recorded.** Follow the model's manual;
   do not assume a generic power-cycle sequence or an `ITEAD-` network name.
2. Connect your computer to the bulb's actual setup Wi-Fi, using the setup
   password from its manual if needed. Losing internet while connected is
   expected. Keep the connection despite the operating system's warning;
   temporarily stop automatic network switching or a VPN if it interferes.
   The tested setup gateway was **`10.10.7.1`**. This is a factory setup address,
   not the bulb's eventual address on your home network. Your computer receives
   an address from the bulb; do not assume a particular client address.
3. **Read the ID and key before sending Wi-Fi configuration.** The setup network
   disappears when the bulb joins yours, so collect the values in this window.
   Run this locally on the computer connected to the bulb:

   ```sh
   curl -v http://10.10.7.1/device \
     -H "Accept: application/json" \
     -H "Content-Type: application/json;charset=UTF-8" \
     -H "Package-Name: com.coolkit" \
     -H "Cache-Control: no-store"
   ```

   The tested response has these fields. All values below are placeholders:

   ```json
   {
     "deviceid": "<your-bulb-device-id>",
     "apikey": "<your-bulb-device-key>",
     "chipid": "<chip-id>",
     "accept": "post"
   }
   ```

   Save `deviceid` and `apikey` in a password manager or your own secret store.
   `apikey` is the HA device key; `chipid`, the MAC and the Wi-Fi SSID are not.
   Do not commit the response or publish it in issues or screenshots.
4. Provision the bulb onto your **2.4 GHz Wi-Fi**. The following local request
   was tested on one bulb as an alternative to account-based app provisioning:

   ```sh
   curl -v http://10.10.7.1/ap \
     -H "Accept: application/json" \
     -H "Content-Type: application/json;charset=UTF-8" \
     -H "Package-Name: com.coolkit" \
     -H "Cache-Control: no-store" \
     -d '{"ssid":"YOUR_SSID","password":"YOUR_PASSWORD","serverName":"cn-disp.coolkit.invalid","port":8080}'
   ```

   Replace only the SSID/password placeholders with your own values locally.
   In a POSIX shell, outer single quotes prevent `$` and `!` from being expanded.
   Credentials containing a single quote need different shell quoting, and
   embedded double quotes/backslashes must still be escaped correctly in JSON.
   The completed command contains your Wi-Fi password: keep it out of shell
   history, logs, shared terminal recordings and Git.
   `-v` adds connection/request diagnostics; the response still contains private
   device credentials. Keep the terminal output private too.

   The `.invalid` name deliberately cannot resolve in normal DNS, preventing
   registration through that configured cloud endpoint. On the tested bulb it
   joined Wi-Fi, accepted LAN commands and was observed without cloud contact.
   This is a result for that bulb/firmware, not a universal network-isolation
   guarantee. The integration itself does not make cloud requests.
5. **Verify that the bulb actually joined.** A response of `{"error":0}` means
   the request was accepted, not that Wi-Fi authentication succeeded. During
   testing, an incorrect Wi-Fi password also returned success while the bulb
   never joined. Reconnect your computer to the normal network and look for
   the bulb in the router's DHCP leases. Do not proceed on the response alone.
6. Reserve the bulb's normal LAN address in DHCP. Match the correct bulb in the
   lease list; do not enter the factory setup address as its HA host.
7. Record **name, normal LAN IP, device ID and device key** securely. In HA,
   open **Settings → Devices & services → Add integration → eWeLink LAN
   Light (no cloud)** and enter a name, that LAN address, the device ID and key.
   Repeat separately for every bulb. HA must be able to reach the bulb's
   LAN endpoint on TCP port 8081; mDNS is used for pushed state updates.

## What was actually tested

The cloud-free `/ap` request with the `.invalid` server name was tested on **one
bulb**. Two older bulbs were initially provisioned through the regular eWeLink
app and associated with an account; their keys were also obtained from `/device`
while in pairing mode. That does not establish that the cloud-free provisioning
request was tested on those older bulbs. No personal bulb addresses or actual
credential values are included here.

Treat the device key as a password: it permits control of that bulb from a
reachable LAN client. After a factory reset, read it again rather than assuming
it stayed the same; key persistence across resets has not been verified.

## If retrieval or setup fails

- **No setup Wi-Fi:** confirm the model's AP/compatible mode rather than quick
  pairing, and check that the pairing window has not expired.
- **The page does not open:** confirm you are still on the bulb's Wi-Fi and
  using HTTP and the correct setup gateway. Do not disable your firewall globally.
- **404, no `apikey`, or a different response:** this firmware may not expose the
  method. Do not guess credentials; check model-specific documentation or an
  existing authorized secret record. Cloud-account keys are not interchangeable.
- **HA cannot connect:** check the normal LAN address, routing and TCP 8081.
  In this implementation a non-response can also mean a busy device or wrong
  key, so it does not conclusively distinguish authentication from connectivity.
- **`/ap` returns success but no DHCP lease appears:** recheck the SSID, password
  and 2.4 GHz network. Request acceptance is not proof of Wi-Fi connectivity.
- **A reset/re-pair breaks a previous entry:** confirm whether the address or key
  changed, then update/reconfigure the affected entry using supported HA controls.

The config flow validates against the bulb locally. Its empty `switch` payload
is intended to avoid changing power state; completing setup is not proof that
every lighting function works. Confirm real control during an appropriate test.

## References and scope

The [SonoffLAN maintainer's manual device-key instructions](https://github.com/AlexxIT/SonoffLAN#getting-devicekey-manually)
document the setup-network `/device` route and the mapping from `apikey` to
`devicekey`. That supports the retrieval method; it is not a compatibility
guarantee for every bulb. This repository's implementation has been exercised
on BL602 CK0205PWM bulbs. The detailed `/ap` recipe and observations above come
from the operator's test report; the referenced manual key-retrieval guide does
not establish that provisioning recipe. Check your product manual before
entering pairing mode.
