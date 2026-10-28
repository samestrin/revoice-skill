import io
import os
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from _load import SKILL, load, run_main

SCRIPT = SKILL / "sync.py"


class HelpTest(unittest.TestCase):
    def test_help_exits_zero_without_config_or_pyyaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            # A yaml module that fails on import proves --help never imports it,
            # and an empty HOME proves it never reads the config.
            (Path(tmp) / "yaml.py").write_text("raise ImportError('yaml must not be imported')\n")
            env = {**os.environ, "PYTHONPATH": tmp, "HOME": tmp, "USERPROFILE": tmp}
            proc = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                                  capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("usage:", proc.stdout)
        self.assertIn("SilverBullet", proc.stdout)

    def test_imports_without_pyyaml(self):
        with mock.patch.dict(sys.modules, {"yaml": None}):
            load(SCRIPT, "sync_no_yaml")


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.sync = load(SCRIPT, "sync")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.config = self.dir / "config.yaml"
        self.config.write_text("stub; parsed by the fake yaml\n")
        self.assets = self.dir / "voices"
        self.cfg = {
            "sb_url": "http://sb.test/",
            "voices": {"alex": {"sb_source": "Voices/Alex.md"},
                       "jordan": {"sb_source": "Voices/Jordan.md"}},
            "audiences": ["work", "family"],
        }
        self.notes = {
            "Voices/Alex.md": b"alex base",
            "Voices/Alex (work).md": b"alex work",
            "Voices/Jordan.md": b"jordan base",
        }
        self.fetched = []
        fake_yaml = types.ModuleType("yaml")
        fake_yaml.safe_load = lambda f: self.cfg
        for p in (mock.patch.object(self.sync, "CONFIG", str(self.config)),
                  mock.patch.object(self.sync, "VOICES", str(self.assets)),
                  mock.patch.object(self.sync, "fetch", self.fake_fetch),
                  mock.patch.dict(sys.modules, {"yaml": fake_yaml})):
            p.start()
            self.addCleanup(p.stop)

    def fake_fetch(self, sb_url, note):
        self.fetched.append((sb_url, note))
        return self.notes.get(note)

    def run_sync(self, *argv):
        err = io.StringIO()
        with redirect_stderr(err):
            code, out = run_main(self.sync, *argv)
        return code, out, err.getvalue()

    def asset(self, name):
        return (self.assets / name).read_bytes()

    def test_syncs_every_voice_and_existing_overlays(self):
        code, out, _ = self.run_sync()
        self.assertEqual(code, 0)
        self.assertEqual(sorted(os.listdir(self.assets)), ["alex-work.md", "alex.md", "jordan.md"])
        self.assertEqual(self.asset("alex.md"), b"alex base")
        self.assertEqual(self.asset("alex-work.md"), b"alex work")
        self.assertIn("SKIPPED  alex-family.md (no note: Voices/Alex (family).md)", out)

    def test_slug_argument_syncs_only_that_voice(self):
        code, _, _ = self.run_sync("jordan")
        self.assertEqual(code, 0)
        self.assertEqual(os.listdir(self.assets), ["jordan.md"])
        self.assertTrue(all(note.startswith("Voices/Jordan") for _, note in self.fetched))

    def test_unknown_slug_is_an_error(self):
        code, _, err = self.run_sync("nobody")
        self.assertEqual(code, 1)
        self.assertIn("voice 'nobody' is not in config", err)
        self.assertEqual(self.fetched, [])

    def test_missing_sb_url_is_an_error(self):
        del self.cfg["sb_url"]
        code, _, err = self.run_sync()
        self.assertEqual(code, 1)
        self.assertIn("sb_url is not set", err)

    def test_missing_base_note_fails_that_voice_only(self):
        del self.notes["Voices/Alex.md"]
        code, out, _ = self.run_sync()
        self.assertEqual(code, 1)
        self.assertIn("MISSING  alex: Voices/Alex.md", out)
        self.assertEqual(os.listdir(self.assets), ["jordan.md"])

    def test_extra_arguments_are_rejected(self):
        with self.assertRaises(SystemExit) as cm, redirect_stderr(io.StringIO()):
            run_main(self.sync, "alex", "jordan")
        self.assertEqual(cm.exception.code, 2)

    def test_missing_pyyaml_is_a_clear_error(self):
        with mock.patch.dict(sys.modules, {"yaml": None}):
            code, _, err = self.run_sync()
        self.assertEqual(code, 1)
        self.assertIn("pip install pyyaml", err)

    def test_slug_that_is_not_a_plain_name_is_refused(self):
        self.cfg["voices"] = {"../escape": {"sb_source": "Voices/Alex.md"},
                              "jordan": {"sb_source": "Voices/Jordan.md"}}
        code, out, _ = self.run_sync()
        self.assertEqual(code, 1)
        self.assertIn("INVALID  ../escape", out)
        self.assertEqual(os.listdir(self.assets), ["jordan.md"])
        self.assertFalse((self.dir / "escape.md").exists())
        self.assertNotIn(("http://sb.test/", "Voices/Alex.md"), self.fetched)

    def test_missing_config_is_a_clear_error(self):
        self.config.unlink()
        code, _, err = self.run_sync()
        self.assertEqual(code, 1)
        self.assertIn(str(self.config), err)


def tree(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


class VoicesDirTest(unittest.TestCase):
    """Voices live in ~/.config/revoice/voices/, outside the skill folder that a
    plugin update replaces."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        env = mock.patch.dict(os.environ, {"HOME": str(self.home), "USERPROFILE": str(self.home)})
        env.start()
        self.addCleanup(env.stop)
        # Loaded after HOME is patched, so its paths resolve under the fake home.
        self.sync = load(SCRIPT, "sync_home")
        self.voices = self.home / ".config" / "revoice" / "voices"

    def test_paths_are_under_the_user_config(self):
        self.assertEqual(Path(self.sync.VOICES), self.voices)
        self.assertEqual(Path(self.sync.CONFIG), self.home / ".config" / "revoice" / "config.yaml")
        self.assertFalse(hasattr(self.sync, "ASSETS"))

    def test_sync_writes_only_under_the_voices_dir(self):
        Path(self.sync.CONFIG).parent.mkdir(parents=True)
        Path(self.sync.CONFIG).write_text("stub; parsed by the fake yaml\n")
        cfg = {"sb_url": "http://sb.test", "audiences": ["formal"],
               "voices": {"alex": {"sb_source": "Voices/Alex.md"}}}
        notes = {"Voices/Alex.md": b"alex base", "Voices/Alex (formal).md": b"alex formal"}
        fake_yaml = types.ModuleType("yaml")
        fake_yaml.safe_load = lambda f: cfg
        skill_before = tree(SKILL)
        home_before = tree(self.home)
        with mock.patch.object(self.sync, "fetch", lambda url, note: notes.get(note)), \
                mock.patch.dict(sys.modules, {"yaml": fake_yaml}):
            code, out = run_main(self.sync)
        self.assertEqual(code, 0, out)
        written = {k: v for k, v in tree(self.home).items() if home_before.get(k) != v}
        self.assertEqual(written, {
            os.path.join(".config", "revoice", "voices", "alex.md"): b"alex base",
            os.path.join(".config", "revoice", "voices", "alex-formal.md"): b"alex formal",
        })
        self.assertEqual(tree(SKILL), skill_before)


if __name__ == "__main__":
    unittest.main()
