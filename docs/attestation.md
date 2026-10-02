# Receipt integrity

M5 uses the mature `cryptography` implementation of Ed25519. Private keys live
outside the repository under the user's private EACH store; verification takes
a trusted public key separately, not an embedded attacker-controlled key.

The signed manifest includes a canonical hash of the **entire receipt payload**
excluding its own attestation block, plus diagnostic stage hashes. This binds
the actual spec, material declarations, model identity, complete attempt history,
validation/audit results, run identity, assurance, and false certification flags.
Signing only a stored `specHash` would not protect the actual spec object.
The verifier also checks the declared algorithm and trusted key fingerprint.

Receipts from the initial incomplete M5 implementation that lack the receipt
root hash do not pass this stronger verifier. They are retained as historical
evidence, not silently treated as equivalent.

Verification establishes the integrity of signed declarations. It does not
prove execution truth, originality, legal clean-room status, or availability
of external source/model files. The current missing-material test checks removal
of a declared input entry; a portable artifact bundle and in-toto/DSSE envelope
remain deferred rather than being implied by a valid signature.
