# Windows: start from GitHub's source ZIP

Use these instructions if you downloaded **Code → Download ZIP** from GitHub. That download is the source repository. The separate generated test kit adds a kit manifest, synthetic document files, and offline parser wheels. The source ZIP is sufficient for inventory and native folder/staging tests, which generate their own temporary synthetic fixtures.

## First: collect inventory

1. Right-click the downloaded ZIP and select **Extract All**. Work in the extracted files, not inside the ZIP viewer.
2. Open the folder that contains `README.md`, `installer`, `scripts`, and `tests`. Windows extraction may put this inside another folder with the same name.
3. Click File Explorer's address bar, type `powershell`, and press Enter. This opens Windows PowerShell in that folder.
4. Paste this command and press Enter:

```powershell
.\installer\Test-Target.ps1
```

This prints hardware/software inventory as JSON. It does not install anything, change settings, probe the network, or read documents. Python and administrator elevation are not required for this first step. Some inventory values may be unknown without elevation; unknown is a valid result, not a reason to change policy.

If it says the script cannot be found, confirm you are in the folder containing `installer` and that extraction finished. If Windows blocks script execution, retain the error and use the unit's permitted execution process. Do not bypass execution policy or unblock files to force the test. Share only permitted inventory or error metadata, never operational information.

## Next: check approved Python and run folder tests

If an approved native Windows Python is already available, check its version:

```powershell
python --version
```

The tests require **64-bit Python 3.11+**. If the command is unavailable or opens the Microsoft Store, do not install from that prompt; record that an approved runtime is needed. If your approved installation uses the Python launcher instead, `py -3 --version` is an alternative; use `py -3` in place of `python` below. A version result alone does not prove 64-bit architecture; the native runners check that before tests.

Then run:

```powershell
python .\scripts\validate_windows_folders.py
```

No pip, virtual environment, model, GPU runtime, manifest hash, or kit launcher is required for this test. It exercises 11 native folder fixtures in synthetic temporary storage. Failures or skipped fixtures produce nonzero exit and are not acceptance. Keep the summary and relevant synthetic test errors.

The additional six synthetic ACL/staging fixtures, if permitted, use:

```powershell
python .\scripts\validate_windows_installation.py
```

Both runners always leave deployment readiness false. These are validation commands, not an AI installation.

## Which instructions apply?

Do not run `Start-TargetValidation.ps1` or `Verify-TestKit.ps1` against GitHub's source ZIP: those commands require the generated `TEST-KIT-MANIFEST.json` and its independently supplied hash. Do not substitute an invented hash or disable verification. Optional offline document parsing also needs the separate kit's `wheelhouse`.

If you have the generated kit with those files, use [test-kit instructions](WINDOWS-TEST-KIT.md). For source-ZIP testing, begin with the inventory command above. GPU/model provisioning, network isolation, signing, and full installation remain separate work.
