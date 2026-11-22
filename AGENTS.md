# Development servers

Start all local development, test, and preview web servers listening on
`0.0.0.0` (all IPv4 interfaces). Set the framework's host/bind flag or environment
variable explicitly. Verify the listening address after starting or restarting
a server.

For this static site, run `python3 -m http.server 8000 --bind 0.0.0.0` from the
repository root.
