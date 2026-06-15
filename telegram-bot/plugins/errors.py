# No catch-all handler — Pyrogram's dispatcher breaks after first match per group,
# so a bare @Client.on_message() here would silently swallow every message.
