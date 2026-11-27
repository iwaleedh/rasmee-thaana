Rasmee Thaana — Regular, Version 1.007 (release candidate, review round 38)

A Thaana typeface for official Maldivian documents, made to look and set like Faruma.

What matches Faruma:
- Units-per-em, line metrics, advance widths and kerning.
- The fixed fili (vowel mark) positions on Thaana letters.

What is verified against Faruma (HarfBuzz shaping):
- Each line of the 113-line corpus (spec/corpus.txt) gives the same glyphs, advances and offsets in
  both fonts.
- So does each Thaana, Arabic and Latin script run of the mixed-script test lines in
  tools/script_tests.py.
- The exception is a fili typed on an explicit dotted-circle carrier (see below).
- Text outside these verified cases has not been compared. For other text, treat line-break
  equivalence as expected, not proven.

Known differences from Faruma:
- Dotted-circle carrier (U+25CC): with the nine upper fili, the mark sits 175 units higher (a
  y-offset), by design. This follows the font's mark anchor on its redrawn dotted circle.
  - The two lower fili (U+07A8, U+07A9) are positioned exactly as in Faruma.
  - The carrier's 1,229-unit advance is the same, so line width is unchanged.
- U+FDFD (Bismillah): this font maps it to its own glyph, uniFDFD (glyph ID 290). That glyph is a
  separate glyph from the backtick Bismillah, grave (glyph ID 149), but has the same drawing and the
  same 5,509-unit advance. The tested Faruma file has no glyph for U+FDFD.
  - With no font fallback (HarfBuzz alone), Faruma gives .notdef at 2,048 units and this font gives
    5,509.
  - In applications that substitute another font for missing characters, the Faruma width depends
    on the substitute. For example, macOS Core Text uses Geeza Pro, about 13,290 units.
  - Text containing U+FDFD therefore does not set to the same width as in Faruma. This is a
    coverage difference.
- Added coverage: this font maps 118 code points that the audited Faruma does not. The exact list,
  classified, is in spec/added_coverage.json. Its SHA-256 is recorded with the approved baseline.
  baseline_check and the release QA preflight reject an edited or incomplete list, and any row that
  disagrees with the approved cmap or ink. tools/baseline_check.py also asserts the complete cmap
  (278 code points), and tools/script_tests.py prints the additions below U+2100 for a given
  reference. 116 of the additions lie below U+2100:
  - 111 are Windows-1252 Latin characters and punctuation with ink, for example é U+00E9 and € U+20AC.
  - One is the no-break space U+00A0. It is blank and shares the space glyph.
  - Four are invisible bidi and joining controls: ZWNJ U+200C, ZWJ U+200D, LRM U+200E and RLM U+200F.
  - Two further added mappings lie above U+2100: the trademark sign ™ U+2122, which has ink, and the
    U+FDFD Bismillah described above.
  - Text with these characters renders in this font instead of falling back to another font, so its
    widths can differ from a Faruma document that used fallback.
- Naa ޱ (U+07B1): the tested Faruma file maps Naa to a blank glyph, which advances 903 units but draws
  nothing. This font draws a visible Naa at the same 903-unit advance. Spacing is unchanged; text with
  Naa now shows the letter.

Provenance:
- Thaana letters, fili and dots are generated from our own pen-stroke skeletons (src/thaana.py,
  tools/stroke.py).
- Selected edges were then fitted to measured sections of Faruma:
  - Noonu ނ: the slot under the lip and the scoop.
  - Laamu ލ: the branch, the right recess and the diagonal edges.
  - Chaviyani ޗ: the diagonal and its tip.
  - The fili ޭ ޮ ޯ: their outer heels.
  - The Arabic question mark ؟: the inner edge of the hook and the tail.
- The Allah ligature (U+FDF2) is drawn as spline outlines fitted to measured sections of Faruma's
  ligature.
- The Faruma measurements were used with the authorisation of the President's Office, which owns
  Faruma. No Faruma outline points are copied.
- Latin, digits and Western punctuation come from Liberation Serif 2.1.5, which is metric-compatible
  with Times New Roman.
- The Bismillah (typed with ` or U+FDFD) is composed from Amiri 1.003 (OFL).
- Legacy Faruma keyboard conventions are kept: ` gives the Bismillah, [ and ] give quotation marks,
  and the full stop sits at mid-height in Thaana text.

Verification. tools/release_qa.py runs four checks on this file, and each one must pass:
1. tools/shapecheck.py: 113 of 113 corpus lines identical in glyph IDs, advances and offsets.
2. tools/script_tests.py: 54 of 54 known-result assertions:
   - all 11 dotted-circle combinations;
   - separately shaped mixed-script runs;
   - backtick, U+FDF2 and U+FDFD;
   - 20 representative added Latin characters, each shaping to an inked glyph.
3. tools/baseline_check.py: matches the reviewed release recorded in spec/release_baseline.json.
   - The file's SHA-256 must equal the approved digest. Any changed table is named.
   - It also checks each property separately, so a change is reported with its meaning:
     - unitsPerEm and line metrics, name records, kern pairs, and GPOS/GSUB/GDEF;
     - every Unicode cmap subtable, which must agree with each other;
     - per-glyph advances, exact filled areas, ink bounds and decomposed outlines;
     - the seven blank glyphs staying blank;
     - identical outlines for both Bismillah encodings;
     - the placement of every fili on every letter and on the dotted circle, and fili contact with
       their own letter.
   Exact filled area means after the fill rule, so degenerate outlines count as no ink.
4. tools/clearance_full.py: adjacent-cluster contact across 219,024 states, including Naa, measured
   on exact Bézier outlines with shared fili ink counted once:
   - 1,794 contact states, against Faruma's 2,457;
   - 78 states deeper than Faruma, by at most 0.100 unit;
   - 0 failures (contact where Faruma has none, or more than 0.5 unit deeper).
All four checks first validate the TrueType structure (tools/font_checks.py):
- required tables and their minimum lengths;
- name-table record count, string offset and string extents;
- table and whole-file checksums, computed explicitly so that they still hold under python -O or
  PYTHONOPTIMIZE;
- the head magic number and units-per-em;
- an exact loca length with bounded offsets;
- hmtx coverage.

Release QA first validates the candidate and the reference. If the reference is not the audited
Faruma, the summary prints a warning. If any of the four checks fails on the candidate, QA stops with
FAIL.

It then builds 24 broken copies ("controls"). Each run writes its logs and a SUMMARY.txt into a new
directory of its own (--out DIR gives DIR/run-<timestamp>-<random>/), so earlier pass logs are never
mistaken for the current run. SUMMARY.txt is written for every outcome: preflight, candidate, control
generation, controls, internal error, and cancellation. An interrupted run (Ctrl-C) records stage
'cancelled' with result FAIL and exits with status 130.

What the control generator verifies itself. Before any check runs, it reopens each control and
compares the properties below with its source.
- Glyph controls (shifted, lifted, erased, zero-area, blank-symbols, ink-in-space, mirrored-fdfd,
  combined and the two -gate copies):
  - exactly the intended glyph records changed;
  - both Unicode cmap dictionaries, all kern pairs and the hhea ascent, descent and lineGap are
    exactly as intended;
  - head created/modified are unchanged.
- cmap controls: both Unicode cmap dictionaries are exactly the intended ones, and glyph records,
  kern pairs and hhea are unchanged.
- metrics and kerning controls: hhea ascent +100, or exactly one named kern pair +60. Everything
  above is otherwise unchanged.
- Raw-table controls (no-outlines, bad-head, truncated-table, loca-count, and the two reference
  name-table controls) are the only ones checked byte for byte. Every table except the targeted
  one is byte-identical, ignoring head.checkSumAdjustment, which any write recomputes. The checksum
  control differs from the release in exactly one byte.
- Controls saved through fontTools are not byte-isolated. Saving also recalculates derived data,
  which the generator does not compare:
  - loca is regenerated;
  - maxp limits change; with the blank-symbols control, maxPoints fell from 2,071 to 461 and
    maxCompositeContours from 16 to 3;
  - head.flags can change; it went from 7 to 5 when the space glyph changed;
  - the head bounding box (xMin, yMin, xMax, yMax) is recalculated;
  - the derived hhea fields advanceWidthMax, minLeftSideBearing, minRightSideBearing, xMaxExtent and
    numberOfHMetrics are recalculated.
  These are expected consequences of the mutations. Any of them alone would still fail
  baseline_check through the approved digest, and the changed table would be named.

What the checks must prove. Each control must be rejected by the check named below: exit status
exactly 1, the expected diagnostic lines (matched from the start of a line and naming the glyph, code
point, kern pair, subtable or table concerned), and no crash.
- clearance_full:
  - a fili shifted 400 units down;
  - an erased fili outline (preflight: no ink);
  - a zero-area fili outline (preflight: no ink).
- baseline_check:
  - a fili lifted 2,200 units;
  - all 11 fili mappings removed;
  - an erased fili outline;
  - a zero-area fili outline;
  - a blank dotted circle, both Bismillahs and the Allah ligature;
  - the 116 additions below U+2100 removed, from the release-owned list (independent of --ref);
  - hhea ascent +100;
  - one named kern pair changed;
  - U+0780 removed from the Windows (3,1) subtable only;
  - é remapped in the Unicode (0,3) subtable only;
  - ink in the space glyph;
  - a mirrored U+FDFD;
  - five of these changes combined, which must produce every expected diagnostic, including the alias
    mismatch.
- shapecheck:
  - glyf and loca removed;
  - a zeroed head magic number;
  - non-font bytes;
  - a truncated hhea table;
  - a wrong loca length;
  - a checksum error in the name table;
  - a reference whose name records were stripped (passed as --ref);
  - a reference whose version-1 name language tag points outside the table (passed as --ref).
Other checks may also reject a control; their results are logged for information only.

All QA commands, including tools/detail_plates.py, reject unknown or misspelled options, stray arguments and missing option values with a
one-line usage diagnostic and exit status 1; they never silently fall back to a default file. A missing
candidate, reference or baseline file also gives a one-line diagnostic and exit status 1. See
review/r24/, review/r27/, review/r29/, review/r30/, review/r31/, review/r32/, review/r33/ and review/r34/command_tests.txt in the project.
The source bundle can be created from any working directory. tools/make_source_bundle.py resolves the
paths you give on its command line (the archive, the expected font and --checksums FILE) from your
current working directory. It reads its own source inputs (src/, spec/, tools/ and latin/) from the
project root, and fails if a required input is missing.
No automated suite can prove the absence of every possible corruption. Together, the digest match and
the property checks cover every byte of the released file.

Own-letter fili collisions: 0, against Faruma's 2 (tools/clearance.py, 429 pairs).
- clearance.py uses the same strict command line as the other checks (font, --ref, --json) and
  validates both fonts.
- It identifies bases and fili by HarfBuzz cluster, one per character, and fails on any .notdef.
- It reports how many pairs it measured: 429 of 429 in this font, and 418 in Faruma, whose Naa is
  blank.
- It exits with status 1 if this font has an own-letter overlap where Faruma is clear, or if any fili
  or letter in this font is missing or blank. Faruma's blank Naa is allowed for the reference only.

Detail plates (tools/detail_plates.py) are rendered into a staging directory. The plates and their
manifest are then published together by swapping the output directory, so a failed rerun leaves the
previous complete set in place. The output directory must be new or contain only a previous plate set.
A directory holding anything else, such as a review folder, is refused and never replaced. The existing
directory's permissions are kept; a new directory follows your umask. A read-only previous set is
still removed after the swap; if it cannot be, a WARNING names where it remains.

Reproducible build: source_bundle.tgz rebuilds this file byte for byte (see SHA256.txt). Unpack it,
create a clean virtual environment with the tested Python (CPython 3.10.8) and install the pinned
packages, then run the release build chained to the release gate:
  python3.10 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
  PYTHON=.venv/bin/python bash build_and_verify.sh && .venv/bin/python tools/baseline_check.py RasmeeThaana-Regular.ttf
With &&, the gate runs only on a freshly verified build, so an older file can never mask a failed
rebuild. On a mismatch, the build script prints both the built and the expected SHA-256.
This exact sequence, with fresh packages from PyPI, reproduced the approved SHA-256 and passed the
bundled baseline_check (review/r28/clean_venv_build.txt in the project). The script pins the release epoch, the version and hinting,
then checks the result against the approved SHA-256. BUILD.txt lists the same commands, one per line,
ready to paste. tools/make_source_bundle.py verifies the documented build in a clean directory before
it replaces an existing archive, and it refuses to package if any build or QA entry point is missing.
- Without an expected font it verifies the rebuild against the approved digest, so an archive is
  never installed unverified.
- Each invocation uses its own temporary archive, so concurrent repacks cannot install each other's
  output.
- Before installing, it also runs the bundled baseline_check on the rebuilt font inside the unpacked
  archive.
- The installed archive keeps the destination's permissions exactly (0644 for a new file).
- Complete maintainer command, run from the project root:
    .venv/bin/python tools/make_source_bundle.py dist/source_bundle.tgz dist/RasmeeThaana-Regular.ttf --checksums dist/SHA256.txt && (cd dist && shasum -a 256 -c SHA256.txt)
  This repacks and verifies the bundle, publishes it with its checksums, and then verifies the
  published font and archive. The && runs the verification only after a successful repack, so an
  older archive and checksum pair can never make a failed repack look successful.
- Split-directory example: font in A/, archive in B/, checksum file in C/:
    mkdir -p B C && .venv/bin/python tools/make_source_bundle.py B/source_bundle.tgz A/RasmeeThaana-Regular.ttf --checksums C/SHA256.txt && (cd C && shasum -a 256 -c SHA256.txt)
  C/SHA256.txt then lists ../A/RasmeeThaana-Regular.ttf and ../B/source_bundle.tgz. If the archive's
  or the checksum file's directory is missing, the packager names it and stops before writing
  anything, including temporary files.
- Paths given on the command line resolve from your working directory. The bundle's own input files
  (src/, spec/, tools/ and latin/) always resolve from the project root.
- The bundle holds an explicit Rasmee Thaana file list: build entry points, modules, spec files,
  design and review tools, and the Liberation/Amiri inputs. Other deliverables' tools in tools/,
  such as faruma_edit* or noofaru*, are never shipped; the packager lists them as 'not bundled'.
- The archive, the expected font and the checksum file must be three different files. Two paths that
  name the same file, or differ only in letter case (macOS and Windows filesystems ignore case), are
  refused. The archive and checksum paths must not be symbolic links, and the archive path must not
  be a directory. Any of these is refused before anything is written.
- With --checksums FILE, the archive and the checksum file are published together. FILE is resolved
  against your working directory, and its entries are relative to FILE's real directory, with
  symlinks resolved. To verify both, change to FILE's directory and run `shasum -a 256 -c` on FILE
  by name, for example `(cd dist && shasum -a 256 -c SHA256.txt)`. This works even when the font,
  archive and checksum file live in different directories.
- The checksum file is staged before anything is published. If it cannot be installed, the previous
  archive is restored, so the old archive and checksum pair stays consistent.
- Every archive entry carries neutral ownership (uid/gid 0, no user or group names), the release
  timestamp and normalised modes. The gzip header has no timestamp. No personal account data ships,
  and repacking the same inputs gives a byte-identical archive.
- If verification fails, the FAIL line shows the underlying build or baseline_check output.
- build_and_verify.sh runs the build in a clean environment (env -i). Only these reach it:
  - PATH and HOME;
  - the release epoch (SOURCE_DATE_EPOCH=1795737600) and the version (FONT_VERSION=1.007);
  - RASMEE_TEMP_BUILD=1, which only changes the log line to say a temporary file was built and is
    verified next.
  Exported settings such as NO_HINT, FONT_FAMILY or RASMEE_ENTRY_ROUND (an optional design
  experiment in tools/stroke.py) therefore cannot change a release build.
- All tools read and write their JSON and text files as UTF-8 whatever the system locale. Their
  console messages escape any character the terminal encoding cannot show, instead of failing. Both
  documented verification chains pass under an ISO-8859-1 locale with ASCII or Latin-1 console
  encoding (review/r38/command_tests.txt in the project).
- build_and_verify.sh is the only release recipe. It builds into a temporary file and checks its
  SHA-256 before moving it to RasmeeThaana-Regular.ttf. Each failure is reported distinctly:
  BUILD FAILED, DIGEST MISMATCH, or INSTALL FAILED (for example, a directory at the target path).
  On any failure nothing is installed and any existing file is left untouched.
- BUILD.txt shows the bare tools/build.py command only as a labelled build-only reference, writing
  to build-only.ttf. It is not a release build.
- tools/build.py builds into a temporary file, validates it, and installs it atomically.
- It refuses to overwrite a file that holds the approved release with a different build unless
  --replace-approved is given.
- It also refuses to overwrite an existing file unless spec/release_baseline.json holds a valid
  64-hex-digit approved SHA-256. It refuses outright when the output path is a directory.
  --replace-approved overrides the overwrite protection.
- A new baseline is written atomically, so a failed write leaves the previous approved baseline
  intact. It can be recorded only with
  `baseline_check.py APPROVED.ttf --write --ref Faruma.ttf`. This is refused unless --ref is the
  audited Faruma and spec/added_coverage.json is exactly the approved font's additions over it.

Still open: Windows Word with its PDF export, and a physical 12 pt print.

Licence: see OFL.txt. Confirm with the President's Office that an OFL release is intended before
distributing the font publicly.

Install: double-click RasmeeThaana-Regular.ttf and choose Install (Windows/macOS).
