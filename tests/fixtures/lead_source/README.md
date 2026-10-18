# Sender encoding qualification vectors

These public fixtures contain synthetic data and intentionally unverified
signatures. They are encoding vectors, not admission or authentication examples.

For every entry in `vectors.json`, a sender implementation must parse the named
UTF-8 file, serialize the complete envelope to exactly the same bytes (no trailing
newline), and reproduce both recorded SHA-256 digests. The payload digest excludes
the authorization object. Decoding and re-encoding must preserve Unicode without
normalization. Passing only a digest without the byte comparison is insufficient.

`ascii.json`, `canonical-envelope.json`, `controls.json`, `emoji-limit.json` and
`unavailable.json` cover ASCII, mixed Unicode (including decomposed text), JSON
control escapes, a body at the scalar limit, and unavailable content with a null
attachment count. `test_published_sender_vectors` executes this qualification for
the parser implementation. Future sender adoption must run the same vectors
against its own encoder before claiming byte equivalence.
