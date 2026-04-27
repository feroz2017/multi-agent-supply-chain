-- Minimal Prosody config for SPADE
admins = {}

-- Modules
modules_enabled = {
    "roster"; "saslauth"; "tls"; "dialback"; "disco";
    "carbons"; "pep"; "private"; "blocklist"; "vcard";
    "version"; "uptime"; "time"; "ping"; "register";
    "admin_adhoc";
}

modules_disabled = {}

-- Allow registration
allow_registration = true

-- Disable TLS requirement for local development
c2s_require_encryption = false
s2s_require_encryption = false

-- Allow PLAIN auth without TLS (needed for SPADE/slixmpp without cert)
allow_unencrypted_plain_auth = true

-- Logging
log = {
    info = "*console";
}

VirtualHost "localhost"
    authentication = "internal_plain"
