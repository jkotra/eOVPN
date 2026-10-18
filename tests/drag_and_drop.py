import sys
import unittest
import os
import tempfile
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gio, Gtk, Gdk

# Ensure resources and schemas are available
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
gre_path = os.path.join(root_dir, "build/data/com.github.jkotra.eovpn.gresource")
if os.path.exists(gre_path):
    try:
        resource = Gio.resource_load(gre_path)
        Gio.Resource._register(resource)
    except Exception:
        pass
os.environ["GSETTINGS_SCHEMA_DIR"] = os.path.join(root_dir, "data")

from eovpn.main_window import MainWindow
from eovpn.eovpn_base import StorageItem


class DragAndDropTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Gtk.Application(application_id="com.github.jkotra.eovpn.test_dnd")

    def setUp(self):
        self.mw = MainWindow(self.app)
        self.mw.setup()
        self.test_dir = tempfile.mkdtemp(prefix="eovpn_dnd_test_")
        self.mw.EOVPN_OVPN_CONFIG_DIR = self.test_dir
        self.mw.EOVPN_CONFIG_DIR = self.test_dir

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_drop_single_ovpn(self):
        src_path = os.path.join(tempfile.gettempdir(), "test_single.ovpn")
        with open(src_path, "w") as f:
            f.write("client\nremote 1.2.3.4\n")

        fl = Gdk.FileList.new_from_list([Gio.File.new_for_path(src_path)])
        accepted = self.mw.drop_target.emit("drop", fl, 0.0, 0.0)

        self.assertTrue(accepted)
        self.assertIn("test_single.ovpn", os.listdir(self.test_dir))
        configs = self.mw.retrieve(StorageItem.CONFIGS_LIST)
        self.assertIn("test_single.ovpn", configs)
        os.remove(src_path)

    def test_drop_multiple_ovpn(self):
        src1 = os.path.join(tempfile.gettempdir(), "multi1.ovpn")
        src2 = os.path.join(tempfile.gettempdir(), "multi2.ovpn")
        with open(src1, "w") as f:
            f.write("client\n")
        with open(src2, "w") as f:
            f.write("client\n")

        fl = Gdk.FileList.new_from_list([
            Gio.File.new_for_path(src1),
            Gio.File.new_for_path(src2)
        ])
        accepted = self.mw.drop_target.emit("drop", fl, 0.0, 0.0)

        self.assertTrue(accepted)
        self.assertIn("multi1.ovpn", os.listdir(self.test_dir))
        self.assertIn("multi2.ovpn", os.listdir(self.test_dir))
        os.remove(src1)
        os.remove(src2)

    def test_drop_zip_rejected(self):
        src_zip = os.path.join(tempfile.gettempdir(), "configs.zip")
        with open(src_zip, "w") as f:
            f.write("fake zip")

        fl = Gdk.FileList.new_from_list([Gio.File.new_for_path(src_zip)])
        accepted = self.mw.drop_target.emit("drop", fl, 0.0, 0.0)

        self.assertFalse(accepted)
        self.assertNotIn("configs.zip", os.listdir(self.test_dir))
        os.remove(src_zip)

    def test_drop_non_ovpn_rejected(self):
        src_txt = os.path.join(tempfile.gettempdir(), "notes.txt")
        with open(src_txt, "w") as f:
            f.write("hello")

        fl = Gdk.FileList.new_from_list([Gio.File.new_for_path(src_txt)])
        accepted = self.mw.drop_target.emit("drop", fl, 0.0, 0.0)

        self.assertFalse(accepted)
        self.assertNotIn("notes.txt", os.listdir(self.test_dir))
        os.remove(src_txt)

    def test_drop_mixed_ovpn_and_zip(self):
        src_ovpn = os.path.join(tempfile.gettempdir(), "mixed.ovpn")
        src_zip = os.path.join(tempfile.gettempdir(), "mixed.zip")
        with open(src_ovpn, "w") as f:
            f.write("client\n")
        with open(src_zip, "w") as f:
            f.write("fake zip")

        fl = Gdk.FileList.new_from_list([
            Gio.File.new_for_path(src_ovpn),
            Gio.File.new_for_path(src_zip)
        ])
        accepted = self.mw.drop_target.emit("drop", fl, 0.0, 0.0)

        self.assertTrue(accepted)
        self.assertIn("mixed.ovpn", os.listdir(self.test_dir))
        self.assertNotIn("mixed.zip", os.listdir(self.test_dir))
        os.remove(src_ovpn)
        os.remove(src_zip)


if __name__ == "__main__":
    unittest.main()
