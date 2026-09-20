# Desktop Lonk Birds

This package runs the local XC Desktop Lonk and Pip birds on Windows. They remember conversations and explicitly shared local files, support taught replies, and keep their state under `%LOCALAPPDATA%\DesktopLonkXC`.

The package includes the repaired flock coordinator and the XC Procedures runtime it needs. It does not use a network service or upload files.

## Install and launch

From PowerShell after cloning `wet_server`:

```powershell
cd .\wet_server\desktop-lonk-birds\desktop-pet
python -m pip install --target vendor -r requirements.txt
python desktop_pet.py
```

The bundled `Start Desktop Lonk Birds.cmd` can be double-clicked after installation.

To open chat at launch:

```powershell
python desktop_pet.py --chat
```

To run the non-window smoke check:

```powershell
python desktop_pet.py --gui-smoke
```

Python 3.14 with Tk is required. The birds are a transparent local associative learner, not a hosted LLM. Their behavior is defined by `DesktopLonk.xc` and the local Python host.