# Source authentication known-answer vectors

Entirely synthetic; the public test seed is bytes(range(32)), never a production credential.
The ASCII and Unicode payloads come unchanged from the existing source encoding fixtures.
Generated before auth.py existed using Python json.dumps(sort_keys=True, separators=(",", ":"),
ensure_ascii=False), hashlib.sha256, and cryptography Ed25519PrivateKey.from_private_bytes.
The preimage is the ASCII encoding of the four LF-separated contract lines, no trailing LF.
The complete preimage, payload digest, raw public key and signature are frozen here.
Tests compare against these literals; they never regenerate expected values using auth.py.
Existing parser encoding vectors remain unchanged. These prove a library boundary only.
