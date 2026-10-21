# Security

Keep device keys and HA/GitHub credentials outside source control. Enter bulb
credentials only in HA configuration. Never commit HA `.storage`, configuration
backups, personal dashboards, logs or credential files. The included ignore rules
are defense in depth; inspect every staged file and scan full history before push.

Use private reporting for credential disclosures. Do not place credentials in
issues. Rotate a disclosed secret immediately.
