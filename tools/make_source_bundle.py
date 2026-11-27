"""Self-contained release source bundle for Rasmee Thaana, verified before it replaces anything.

usage: make_source_bundle.py OUT.tgz [expected.ttf] [--checksums SHA256.txt]
With --checksums the archive and its checksum file are published together: right after the verified archive is
installed, the checksum file (expected font + archive) is rewritten atomically. Entries are relative to the checksum
file's real directory (symlinks resolved). The archive, expected font and checksum file must be distinct files (same
inode, or same path ignoring case, is refused); the archive and checksum paths must not be symbolic links, and the
archive path must not be a directory. Command-line paths resolve from the caller's working directory; bundle inputs
resolve from the project root.
Bundle contents are an explicit Rasmee Thaana inventory (ENTRY_POINTS, MODULES, SPEC, DEV_TOOLS, INPUTS); other files in
tools/, src/ or spec/ (e.g. faruma_edit*, noofaru*) are never shipped and are listed as 'not bundled'.
Without expected.ttf the rebuild is verified against the approved release digest in spec/release_baseline.json,
so a bundle is never installed unverified.

Contents (exactly these; 42 entries):
- src/thaana.py; the spec files in SPEC; the tools in ENTRY_POINTS, MODULES and DEV_TOOLS (build, QA, design and
  review tools of Rasmee Thaana only, NOT every tools/*.py);
- the exact Liberation Serif and Amiri inputs with their licences, and OFL.txt;
- requirements.txt (pinned versions);
- BUILD.txt (copy-pasteable commands and input hashes);
- build_and_verify.sh (the pinned reproducible build plus a digest check).

Safety:
- Every documented build and QA entry point and every required input must exist before anything is written,
  and the optional expected TTF must exist and be readable.
- The archive is written to a unique temporary sibling file (one per invocation). After the documented build reproduces
  the approved font, the bundled tools/baseline_check.py must accept it from inside the unpacked archive.
- The installed archive keeps the destination's permissions exactly (0644 for a new file).
- Archive entries carry neutral ownership (uid/gid 0, no user or group names), the release timestamp and normalised
  modes (0644; 0755 for .sh), and the gzip header timestamp is 0, so no personal account data ships and repacking
  identical inputs gives a byte-identical archive.
- On a verification failure the underlying build or baseline_check output is shown in the FAIL line. It is unpacked in a clean directory and
  build_and_verify.sh is run there exactly as documented. The rebuilt TTF must match expected.ttf byte for byte.
  The QA commands in BUILD.txt are syntax-checked with bash -n.
- Only after all of that succeeds is the temporary archive moved over OUT.tgz with an atomic rename. On any
  failure OUT.tgz is left untouched.
Exit status 0 only on success; every failure is a one-line 'FAIL:' diagnostic."""
import sys, os, tarfile, hashlib, tempfile, subprocess, glob, shutil

for _s in (sys.stdout, sys.stderr):   # diagnostics never fail on a non-UTF-8 console: unencodable text is escaped
    try: _s.reconfigure(errors='backslashreplace')
    except Exception: pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUTS = ['latin/liberation-fonts-ttf-2.1.5/LiberationSerif-Regular.ttf', 'latin/liberation-fonts-ttf-2.1.5/LICENSE',
          'latin/liberation-fonts-ttf-2.1.5/AUTHORS', 'latin/Amiri-1.003/Amiri-Regular.ttf',
          'latin/Amiri-1.003/Amiri-Bold.ttf', 'latin/Amiri-1.003/OFL.txt', 'OFL.txt']
ENTRY_POINTS = ['tools/build.py', 'tools/release_qa.py', 'tools/shapecheck.py', 'tools/script_tests.py',
                'tools/baseline_check.py', 'tools/clearance_full.py', 'tools/clearance.py', 'tools/detail_plates.py',
                'tools/make_source_bundle.py']
MODULES = ['src/thaana.py', 'tools/stroke.py', 'tools/raster.py', 'tools/fitcurves.py', 'tools/font_checks.py']
SPEC = ['spec/metrics.json', 'spec/ref_area.json', 'spec/intentional.json', 'spec/release_baseline.json',
        'spec/added_coverage.json', 'spec/corpus.txt']
# Rasmee Thaana design and review tools (not needed to build, shipped for transparency)
DEV_TOOLS = ['tools/review_sheets.py', 'tools/compare.py', 'tools/witness.py', 'tools/clearance_adj.py',
             'tools/counters.py', 'tools/preview.py', 'tools/sheet.py', 'tools/massing_opt.py', 'tools/extract_metrics.py',
             'tools/holes_src.py', 'tools/test_fitcurves.py', 'tools/scorecard.py']
PINS = ['fonttools==4.65.0', 'shapely==2.1.2', 'numpy==2.2.6', 'uharfbuzz==0.56.4', 'ttfautohint-py==0.6.1',
        'skia-pathops==0.9.2', 'pillow==12.3.0', 'freetype-py==2.5.1']
RELEASE_EPOCH = '1795737600'      # 2026-11-27 00:00 UTC: head.created/modified of the approved release
RELEASE_VERSION = '1.007'
TESTED_PYTHON = 'CPython 3.10.8'


def sha(p):
    with open(p, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def fail(msg):
    print('FAIL:', msg); sys.exit(1)


def build_script(expected_sha):
    return f"""#!/usr/bin/env bash
# THE release recipe: reproducible build of RasmeeThaana-Regular.ttf, digest check, then install.
# Pinned: release epoch {RELEASE_EPOCH}, version {RELEASE_VERSION}, hinting enabled. The build runs in a clean environment
# (env -i): only PATH, HOME and these settings reach it, so no exported override (NO_HINT, FONT_FAMILY, RASMEE_*, ...)
# can change a release build.
# The font is built into a temporary file and verified; only a matching file is moved to RasmeeThaana-Regular.ttf.
# Each failure is reported distinctly (BUILD FAILED / DIGEST MISMATCH / INSTALL FAILED); on any failure nothing is
# installed and any existing RasmeeThaana-Regular.ttf is left untouched.
set -uo pipefail
cd "$(dirname "$0")"
PY="${{PYTHON:-python3}}"
if [ -d RasmeeThaana-Regular.ttf ]; then echo "INSTALL FAILED: RasmeeThaana-Regular.ttf is a directory" >&2; exit 1; fi
TMP="$(mktemp .RasmeeThaana-Regular.XXXXXX)" || {{ echo "BUILD FAILED: cannot create a temporary file" >&2; exit 1; }}
trap 'rm -f "$TMP" "$TMP.ttf"' EXIT
env -i PATH="$PATH" HOME="$HOME" SOURCE_DATE_EPOCH={RELEASE_EPOCH} FONT_VERSION={RELEASE_VERSION} RASMEE_TEMP_BUILD=1 "$PY" tools/build.py --replace-approved "$TMP.ttf" \
  || {{ echo "BUILD FAILED: tools/build.py exited with an error; nothing installed" >&2; exit 1; }}
"$PY" -c 'import hashlib,sys; d=hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest(); print("built    " + d); print("expected " + sys.argv[2]); sys.exit(0 if d==sys.argv[2] else 1)' "$TMP.ttf" {expected_sha} \
  || {{ echo "DIGEST MISMATCH: the build does not match the approved release; nothing installed" >&2; exit 1; }}
mv -f "$TMP.ttf" RasmeeThaana-Regular.ttf \
  || {{ echo "INSTALL FAILED: could not move the verified build to RasmeeThaana-Regular.ttf" >&2; exit 1; }}
echo "digest matches the approved release; installed RasmeeThaana-Regular.ttf"
"""


QA_COMMANDS = """.venv/bin/python tools/baseline_check.py RasmeeThaana-Regular.ttf
.venv/bin/python tools/clearance.py RasmeeThaana-Regular.ttf --ref Faruma.ttf
.venv/bin/python tools/shapecheck.py RasmeeThaana-Regular.ttf --ref Faruma.ttf --corpus spec/corpus.txt
.venv/bin/python tools/script_tests.py RasmeeThaana-Regular.ttf --ref Faruma.ttf
.venv/bin/python tools/clearance_full.py RasmeeThaana-Regular.ttf --ref Faruma.ttf
.venv/bin/python tools/detail_plates.py RasmeeThaana-Regular.ttf plates --ref Faruma.ttf
.venv/bin/python tools/release_qa.py RasmeeThaana-Regular.ttf --ref Faruma.ttf --out qa-logs
"""


def build_txt(expected_sha):
    return ("Rasmee Thaana source bundle\n\n"
            f"1. Create a clean virtual environment with the tested Python ({TESTED_PYTHON}) and install the pinned packages:\n\n"
            "python3.10 -m venv .venv\n"
            ".venv/bin/python -m pip install -r requirements.txt\n\n"
            "2. Release build: build_and_verify.sh is the ONLY release recipe. It pins the release epoch, version and\n"
            "   hinting, checks the SHA-256 and installs only a matching font. Then run the release gate:\n\n"
            "PYTHON=.venv/bin/python bash build_and_verify.sh && .venv/bin/python tools/baseline_check.py RasmeeThaana-Regular.ttf\n\n"
            "   The two steps are chained with &&: the gate runs only on a freshly verified build, so an older\n"
            "   RasmeeThaana-Regular.ttf can never mask a failed rebuild.\n\n"
            "   For reference only, the BUILD-ONLY command it wraps is shown below. It does no digest check and is not a\n"
            "   release build; do not ship its output without the chained command above:\n\n"
            f"env -i PATH=\"$PATH\" HOME=\"$HOME\" SOURCE_DATE_EPOCH={RELEASE_EPOCH} FONT_VERSION={RELEASE_VERSION} .venv/bin/python tools/build.py build-only.ttf\n\n"
            f"   Expected SHA-256 of RasmeeThaana-Regular.ttf: {expected_sha or '(not recorded)'}\n\n"
            "3. QA. Faruma is NOT included; it belongs to the President's Office. Reviewers with authorised access\n"
            "   save it as Faruma.ttf beside this file. The audited file has SHA-256\n"
            "   ff5985587f10897623704d8269b83e9f63e49dd58625078cac81204ee4d797e5.\n"
            "   baseline_check needs no Faruma. release_qa runs all four checks and 24 designated, self-verified\n"
            "   controls. Every command exits with status 1 on any failure, invalid or missing input, or unknown option.\n"
            "   release_qa interrupted with Ctrl-C writes a 'cancelled' SUMMARY.txt and exits with status 130.\n\n"
            + QA_COMMANDS +
            "\nInput SHA-256:\n" + ''.join(f'{sha(f)}  {f}\n' for f in INPUTS))


def main():
    from argparse import ArgumentParser
    class P(ArgumentParser):
        def error(self, m): fail(f'usage: {m}')
    ap = P(prog='make_source_bundle.py', allow_abbrev=False); ap.add_argument('out'); ap.add_argument('expected', nargs='?')
    ap.add_argument('--checksums', help='after installing the verified archive, atomically rewrite this SHA256 file '
                                        '(expected font + archive), so both are published together')
    a = ap.parse_args()
    if a.checksums and not a.expected:
        fail('--checksums needs the expected font so both digests can be recorded (nothing written)')
    ck = os.path.abspath(a.checksums) if a.checksums else None   # resolved against the caller's working directory
    if ck and not os.path.isdir(os.path.dirname(ck)):
        fail(f'checksum file directory does not exist: {os.path.dirname(ck)} (nothing written)')
    out = os.path.abspath(a.out); expected = os.path.abspath(a.expected) if a.expected else None
    # path collisions: the archive, the expected font and the checksum file must be three different files
    def same(a_, b_):
        """True if two paths name the same file: identical inode when both exist; otherwise a case-insensitive
        comparison of the resolved paths (macOS/Windows filesystems are usually case-insensitive)."""
        if os.path.exists(a_) and os.path.exists(b_):
            return os.path.samefile(a_, b_)
        return os.path.realpath(a_).casefold() == os.path.realpath(b_).casefold()
    for label, p_ in (('archive', out), ('checksum file', ck)):
        if p_ and os.path.islink(p_):   # outputs must be real files, so the manifest names the published path
            fail(f'{label} path {p_} is a symbolic link; give the real path (nothing written)')
    trio = [('archive', out), ('expected font', expected), ('checksum file', ck)]
    for i, (na, pa) in enumerate(trio):
        for nb, pb in trio[i + 1:]:
            if pa and pb and same(pa, pb):
                fail(f'{na} and {nb} are the same file ({pa} / {pb}); nothing written')
    if os.path.isdir(out):
        fail(f'archive path {out} is a directory; nothing written')
    if not os.path.isdir(os.path.dirname(out)):   # checked before any temporary work is allocated
        fail(f'archive directory does not exist: {os.path.dirname(out)} (create it first, e.g. mkdir -p; nothing written)')
    if expected and not os.path.isfile(expected):
        fail(f'expected font not found: {expected} (nothing written)')
    if expected:
        expected_sha = sha(expected)
    else:   # default: the approved release digest recorded in the baseline; the bundle is always verified
        import json
        try:
            expected_sha = json.load(open(os.path.join(ROOT, 'spec', 'release_baseline.json'), encoding='utf-8'))['font_sha256']
        except Exception as e:
            fail(f'no expected font given and the approved digest could not be read from spec/release_baseline.json ({e!r}); nothing written')
    os.chdir(ROOT)   # collect files relative to the project root, whatever the caller's working directory
    missing = [f for f in INPUTS + ENTRY_POINTS + MODULES + SPEC + DEV_TOOLS if not os.path.isfile(f)]
    if missing:
        fail(f'required bundle input(s) missing: {missing} (nothing written)')
    # explicit Rasmee Thaana inventory: other deliverables' tools in tools/ (e.g. faruma_edit*, noofaru*) never ship here
    files = sorted(set(ENTRY_POINTS + MODULES + SPEC + DEV_TOOLS)) + INPUTS
    excluded = sorted(set(glob.glob('tools/*.py') + glob.glob('src/*.py') + glob.glob('spec/*')) - set(files))
    if excluded: print('not bundled (not part of Rasmee Thaana):', ', '.join(excluded))
    work = tempfile.mkdtemp(prefix='bundle-')
    fd, tmp_archive = tempfile.mkstemp(prefix='.' + os.path.basename(out) + '.', suffix='.tmp', dir=os.path.dirname(out) or '.')
    os.close(fd)   # unique per invocation: concurrent repacks never share or install each other's archive
    try:
        for name, text in (('requirements.txt', '\n'.join(PINS) + '\n'), ('BUILD.txt', build_txt(expected_sha)),
                           ('build_and_verify.sh', build_script(expected_sha))):
            with open(os.path.join(work, name), 'w', encoding='utf-8') as f: f.write(text)
        import gzip
        def neutral(ti):   # no personal account names or local timestamps in the release archive; reproducible
            ti.uid = ti.gid = 0; ti.uname = ti.gname = ''
            ti.mtime = int(RELEASE_EPOCH)
            ti.mode = 0o755 if ti.name.endswith('.sh') else 0o644
            return ti
        with open(tmp_archive, 'wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as gz, \
                tarfile.open(fileobj=gz, mode='w', format=tarfile.PAX_FORMAT) as t:
            for f in files: t.add(f, arcname=f, filter=neutral)
            for name in ('requirements.txt', 'BUILD.txt', 'build_and_verify.sh'):
                t.add(os.path.join(work, name), arcname=name, filter=neutral)
        # verify the temporary archive exactly as a user would use it
        d = tempfile.mkdtemp(prefix='bundle-check-')
        try:
            with tarfile.open(tmp_archive) as t: t.extractall(d)
            r = subprocess.run(['bash', '-n', '-c', QA_COMMANDS], capture_output=True, text=True, encoding='utf-8', errors='replace')
            if r.returncode: fail(f'documented QA commands are not valid shell: {r.stderr.strip()}')
            for need in ENTRY_POINTS + MODULES + SPEC:
                if not os.path.isfile(os.path.join(d, need)): fail(f'archive lacks {need}')
            if True:   # always verify: against expected.ttf, or the approved digest by default
                env = {k: v for k, v in os.environ.items() if k not in ('NO_HINT', 'SOURCE_DATE_EPOCH', 'FONT_VERSION')}
                env['PYTHON'] = sys.executable
                r = subprocess.run(['bash', 'build_and_verify.sh'], cwd=d, capture_output=True, text=True, encoding='utf-8', errors='replace', env={**env, 'PYTHONIOENCODING': 'utf-8'})
                got = sha(os.path.join(d, 'RasmeeThaana-Regular.ttf')) if os.path.isfile(os.path.join(d, 'RasmeeThaana-Regular.ttf')) else None
                print('rebuild ', got); print('expected', expected_sha)
                if r.returncode or got != expected_sha:
                    detail = ' | '.join([l for l in (r.stdout + r.stderr).strip().splitlines() if 'pinhole' not in l][-6:])
                    fail(f'documented build did not reproduce the expected font (exit {r.returncode}): {detail}; {out} left unchanged')
                print('BYTE-IDENTICAL (via build_and_verify.sh as documented)')
                # the bundled release gate must accept the rebuilt font from inside the unpacked archive
                r = subprocess.run([sys.executable, '-I', 'tools/baseline_check.py', 'RasmeeThaana-Regular.ttf'], cwd=d,
                                   capture_output=True, text=True, encoding='utf-8', errors='replace', env={**env, 'PYTHONIOENCODING': 'utf-8'})
                if r.returncode:
                    detail = ' | '.join((r.stdout + r.stderr).strip().splitlines()[:8])
                    fail(f'bundled baseline_check rejected the rebuilt font (exit {r.returncode}): {detail}; {out} left unchanged')
                print('bundled baseline_check: ' + r.stdout.strip().splitlines()[-1])
        finally:
            shutil.rmtree(d, ignore_errors=True)
        mode = (os.stat(out).st_mode & 0o7777) if os.path.exists(out) else 0o644
        os.chmod(tmp_archive, mode)   # exactly the destination's existing mode (0644 for a new file); mkstemp made 0600
        tmpck = backup = None
        try:
            if ck:   # stage the checksum file BEFORE publishing anything; paths are relative to the checksum file
                ckdir = os.path.dirname(ck)
                rdir = os.path.realpath(ckdir)   # symlinks resolved, so the relative paths hold for shasum -c
                text = (f'{sha(expected)}  {os.path.relpath(os.path.realpath(expected), rdir)}\n'
                        f'{sha(tmp_archive)}  {os.path.relpath(os.path.realpath(out), rdir)}\n')
                fd2, tmpck = tempfile.mkstemp(prefix='.' + os.path.basename(ck) + '.', dir=ckdir)
                with os.fdopen(fd2, 'w', encoding='utf-8') as fh: fh.write(text)
                os.chmod(tmpck, (os.stat(ck).st_mode & 0o7777) if os.path.exists(ck) else 0o644)
                if os.path.exists(out):   # keep the previous archive so the old pair can be restored
                    fd3, backup = tempfile.mkstemp(prefix='.' + os.path.basename(out) + '.', suffix='.prev', dir=os.path.dirname(out))
                    os.close(fd3); shutil.copy2(out, backup)
            os.replace(tmp_archive, out)   # atomic: only a verified archive replaces the destination
            if tmpck:
                try:
                    os.replace(tmpck, ck)
                except Exception as e:
                    if backup: os.replace(backup, out)
                    else: os.remove(out)
                    fail(f'checksum file could not be installed ({e!r}); previous archive and checksum pair restored')
            print('bundle', out, len(files) + 3, 'files')
            if ck: print('checksums', ck); print(text.rstrip())
        finally:
            for p_ in (tmpck, backup):
                if p_ and os.path.exists(p_): os.remove(p_)
    finally:
        shutil.rmtree(work, ignore_errors=True)
        if os.path.exists(tmp_archive): os.remove(tmp_archive)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        fail(f'internal error {e!r}; destination left unchanged')
