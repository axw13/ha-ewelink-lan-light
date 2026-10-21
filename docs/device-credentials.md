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

## Existing working bulbs

An existing HA entry already has the ID and key. Updating this integration does
not require collecting them again. Reuse an existing securely stored record if
you need to configure another HA installation. Do not reset a working bulb just
to follow this guide: pairing can disrupt control and may change credentials.

## Local pairing-access-point method

This is the local `/device` method referenced by this integration's setup code.
It applies only to firmware that exposes that endpoint in compatible/AP pairing
mode. Other eWeLink, Tuya, LEDVANCE or Matter products may use different methods.

1. Work on one bulb at a time. Follow **that model's manual** to enter
   compatible/AP pairing mode. There is no universal power-cycle sequence;
   quick/Bluetooth pairing alone may not expose a Wi-Fi access point.
2. On your own phone or laptop, join the bulb's temporary setup Wi-Fi. Supported
   eWeLink firmware commonly advertises a name beginning with `ITEAD-`.
   The documented default password for that setup network is `12345678`;
   use the device manual if it specifies another value. This is a manufacturer
   setup default, not your home Wi-Fi password or a private repository secret.
3. Stay connected when the operating system warns that the network has no
   internet. If necessary, temporarily stop mobile-data switching or a VPN so
   requests go to the bulb's Wi-Fi network.
4. Open **`http://10.10.7.1/device`** in a browser connected to that network.
   This is the documented factory setup address, not a home-network address.
   If the model uses another setup address, consult its manual and the gateway
   assigned by its access point. Use plain HTTP, not HTTPS.
5. Read the returned JSON **locally**. The relevant fields look like this;
   these values are deliberately placeholders, not working credentials:

   ```json
   {
     "deviceid": "<your-bulb-device-id>",
     "apikey": "<your-bulb-device-key>"
   }
   ```

   Field nesting can vary by firmware. Copy `deviceid` as the device ID and
   `apikey` as the device key. A `chipid`, MAC address or Wi-Fi SSID is not the key.
6. Save the two values in a password manager or your own secret store. Do not
   commit the response, paste it into an issue, or publish screenshots of it.
7. Exit setup and reconnect the bulb to its normal Wi-Fi using its supported
   pairing procedure, normally through the eWeLink app. That provisioning step
   is separate from this integration's subsequent local-only control. Return
   your phone/laptop to its normal network afterward.
8. Find the bulb's **normal LAN address** in the router's DHCP lease list.
   Match its device details rather than guessing from another bulb. A DHCP
   reservation helps keep the address stable. Do not enter the factory setup
   address in HA as the bulb's normal host.
9. In HA, open **Settings → Devices & services → Add integration → eWeLink LAN
   Light (no cloud)** and enter a name, that LAN address, the device ID and key.
   Repeat separately for every bulb. HA must be able to reach the bulb's
   LAN endpoint on TCP port 8081; mDNS is used for pushed state updates.

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
on BL602 CK0205PWM bulbs. Check your product manual before entering pairing mode.
