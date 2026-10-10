# SILO

**Super Intelligence for Local Offline Operations**

*Air-gapped intelligence. Anywhere.*

The selected artwork is the original vault-window robot concept: graphite enclosure, prominent corner bolts, silver robot face, teal eyes and amber status light. The later refined mockup was rejected. The selected original PNG is preserved unchanged in `assets/branding/silo.png`; `silo.ico` packages the same artwork at 16, 24, 32, 48, 64, 128 and 256 pixels for Windows shortcuts. No crop, background removal or redesign was applied.

The Windows evaluation app and current-user desktop and Start menu shortcuts use this icon. Release snapshots permit only these two explicit binary asset paths, and installation includes them in the immutable payload manifest. Changes to either installed asset invalidate the release's integrity check. Existing shortcuts pointing to another application are preserved. Rollback to an older release without an icon uses the default shortcut icon.

Existing installation directories, launcher filenames and the internal `local_ai_appliance` Python package retain their names so branding does not move user state or break existing installs.

The host stays connected while contained AI processes are denied external networking. The tagline is branding, not proof of a physical air gap, completed isolation qualification or CUI authorization. The current workstation and evaluation limits still apply. This independent project has no current GenAI.mil affiliation, endorsement or integration.
