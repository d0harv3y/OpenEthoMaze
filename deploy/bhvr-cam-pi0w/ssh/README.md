# NVR SSH trust for bhvr-cam

`nvr_authorized_keys` is the **NVR** session-control public key
(`admin@bhvr-nvr0:~/.ssh/id_ed25519_bhvr.pub`). Public keys only — safe in the
payload.

## How it gets onto a Zero

1. **`apply-to-boot.ps1`** copies this file into `bhvr-cam/ssh/` on the FAT boot
   partition and merges the key into Imager `user-data` when present.
2. **`firstboot/99-bhvr-cam.sh`** installs/merges it into
   `/home/admin/.ssh/authorized_keys` (covers cards where Imager missed the key).

MQTT announce can work without this; **focus live / record SSH cannot**.

Refresh after rotating the NVR key:

```powershell
scp admin@bhvr-nvr0:~/.ssh/id_ed25519_bhvr.pub `
  C:\Users\admin\code\OpenEthoMaze\deploy\bhvr-cam\ssh\nvr_authorized_keys
```
