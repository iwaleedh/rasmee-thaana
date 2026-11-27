Rasmee Thaana — Noofaru style, Version 1.100 (OFL-1.1, see OFL.txt)

Rasmee Thaana (dist/RasmeeThaana-Regular.ttf, the approved release, unchanged) with Noofaru's look:

1. Rounded entry strokes. The faceted pen entry of the 15 entry-stroke letters
   (ހ ށ ނ ރ ޅ އ ވ މ ފ ދ ތ ލ ގ ޔ ޗ and the dotted letters built on them) is rounded into a soft
   blob, made in Rasmee's own stroke engine (tools/stroke.py, RASMEE_ENTRY_ROUND=65,200). As in
   Noofaru, the fili are not rounded. The build's usual fitting then keeps each letter's ink box and
   colour on the reference metrics. No Faruma/Noofaru outline points are copied.
2. 10° left slant, exactly as Noofaru 2.1 (tools/noofaru_slant.py --angle 10): Thaana letters,
   fili and dots shear about y=360; the comma ، leans with the letters; the full stop . and the
   Dhivehi ؟ ؛ lean about their own ink centre (positions unchanged). Fili on letters sit as in the
   release; fili on the dotted circle ◌ sit as in Noofaru. Italic angle 10°, caret slope 2048/-361.
3. Version 1.100 (head, name ID 5 and the unique ID "RasmeeThaana-Regular;1.100"), new modified date.

Unchanged: digits, Latin (Liberation Serif), Arabic incl. ﷲ and Bismillah, advance widths, kerning,
GPOS/GSUB (byte-identical), hinting.

Verified: font_checks valid; shapecheck 113/113 lines identical to the release (glyphs, advances,
offsets); script_tests 54/54; clearance_full 0 gate failures; 48,672 letter+fili pairs with no new
contact; hinted rendering 10–32 px as clean as the release, no hinted width changes.
baseline_check rejects this file by design (it pins the approved release).

Rebuild:
  RASMEE_ENTRY_ROUND=65,200 .venv/bin/python tools/build.py build/rasmee_noofaru/r65.ttf
  .venv/bin/python tools/noofaru_slant.py build/rasmee_noofaru/r65.ttf \
      dist/rasmee-noofaru-style/RasmeeThaana-NoofaruStyle.ttf --angle 10 --version 1.100
Without RASMEE_ENTRY_ROUND, tools/build.py still produces the approved release byte-for-byte.

Note: the family name is still "Rasmee Thaana"; do not install it next to the release build.
