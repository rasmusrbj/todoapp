"""The ``todoapp`` command-line client.

A pure API client: it speaks Connect over HTTP through the *generated* client stubs
and never touches the database. That is deliberate — the CLI exercises the same
contract a browser or a phone would, so anything it can do is something the API
genuinely exposes, and nothing it does can bypass an authorization check.

It lives inside the server package only because ``connect-python`` emits servers and
clients into the same generated module; splitting it out would mean a second
codegen root for no gain.
"""
