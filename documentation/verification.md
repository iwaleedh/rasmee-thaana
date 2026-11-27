# Submission preparation verification

Verified on 2026-11-27 against the supplied version 1.100 font.

- The font in `dist/rasmee-noofaru-style/` is byte-identical to the supplied attachment.
- `tools/rebuild_noofaru.py` succeeded using the original project's CPython 3.10.8 environment and reproduced SHA-256 `56980444a8add9e512fae56f015560a64f2400e543373e1243db7169053476e4` exactly.
- `tools/shapecheck.py dist/rasmee-noofaru-style/RasmeeThaana-NoofaruStyle.ttf --ref dist/RasmeeThaana-Regular.ttf` passed: **113/113 corpus lines** identical in glyph sequence, advances, and offsets. This compares the two Rasmee versions, not Faruma. Both inputs passed the tool's TrueType structure checks. The tool printed its expected warning that the chosen reference is not its default Faruma reference.
- Font metadata and character counts are recorded in `font-inspection.json`.
- The specimen was generated from the supplied version 1.100 TTF using Pillow/RAQM and visually inspected.
- Google Fonts issue searches for “Rasmee” and “Noofaru” returned zero issues.
- `https://namecheck.fontdata.com/?q=Rasmee+Thaana` reported no font with that exact name. This does not establish trademark clearance or exhaustive name uniqueness.
- Fontspector, GF Latin Core coverage validation, a UFO/Fontmake build, and Google product integration tests have **not** been completed.

No Google Fonts acceptance, CLA completion, independently verified third-party permission, or Workspace availability is claimed.
