# Private Source and License Operations

This guide is for the owner and belongs only in `bachhoppo18/slh-source`.

## License Gist

Create a **secret Gist** containing `licenses.json`:

```json
{
  "keys": {},
  "machines": {}
}
```

Ask the user to open the app and send you the machine code shown in the
activation dialog. Generate a key bound to that machine in the private source
checkout:

```bash
python issue_license.py <64-character-machine-code>
```

Send the printed key to that user. Add both printed entries to the matching
objects in the Gist, keeping the key itself out of the Gist:

```json
{
  "keys": {
    "<key-sha256>": "<machine-code>"
  },
  "machines": {
    "<machine-code>": "<key-sha256>"
  }
}
```

The app reads this Gist directly using its raw HTTPS URL; no API host or GitHub
token is needed. The two maps enforce one key per machine and one machine per
key. To revoke a license, remove its entries from both maps. To move a user to
a replacement machine, remove both old entries and issue a new key for the new
machine code. A secret Gist is unlisted, not private: anyone who obtains its
URL can read the hashes and machine codes. Never put raw license keys there.

## Private Source and Public Releases

Keep every Python source file and this guide in the private repository
`bachhoppo18/slh-source`. The public repository `bachhoppo18/slh` contains the
user-facing README, release assets, and the `slh-data/` files used by the app's
list synchronization. If those runtime lists move to another repository,
update `DATA_REPO` in `slhtool.py` before removing `slh-data/` from the public
repo.

Add the Actions secret `SLH_RELEASE_TOKEN`, a fine-grained token limited to the
public `bachhoppo18/slh` repository with Contents read/write access. The private
workflow obfuscates the client with PyArmor, packages it with PyInstaller, and
uploads only the installer and portable ZIP to the public repo's Releases.
PyArmor must be correctly licensed for the app's size and distribution; it
raises the cost of inspection but cannot make a distributed executable
impossible to reverse engineer.

## Existing Public Repository

The current public `bachhoppo18/slh` already contains Python source in its Git
history. Removing files in a new commit does not make those earlier versions
private. Before pushing source changes, create the private repository, copy and
verify the full source there, and decide how to retire or replace the public
repository. A history rewrite/force-push can disrupt clones and cannot guarantee
removal from forks, caches, or copies already downloaded. Do not publish this
source checkout to the current public remote.