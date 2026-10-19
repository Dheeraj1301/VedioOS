import importlib.util
import os
from pathlib import Path
from unittest import TestCase, mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "start_shared_preview.py"
SPEC = importlib.util.spec_from_file_location("start_shared_preview", SCRIPT)
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


class SharedPreviewLauncherTests(TestCase):
    def test_external_storage_is_never_started(self):
        with mock.patch.dict(os.environ, {"S3_ENDPOINT_URL": "https://storage.example.test"}):
            with mock.patch.object(launcher.subprocess, "Popen") as popen:
                self.assertIsNone(launcher.ensure_local_storage())
        popen.assert_not_called()

    def test_running_loopback_storage_is_left_untouched(self):
        with mock.patch.dict(os.environ, {"S3_ENDPOINT_URL": "http://127.0.0.1:9000"}):
            with mock.patch.object(launcher, "_port_is_open", return_value=True):
                with mock.patch.object(launcher.subprocess, "Popen") as popen:
                    self.assertIsNone(launcher.ensure_local_storage())
        popen.assert_not_called()

    def test_missing_loopback_storage_is_started_and_initialized(self):
        process = mock.Mock()
        process.poll.return_value = None
        log = mock.mock_open()
        with mock.patch.dict(os.environ, {"S3_ENDPOINT_URL": "http://localhost:9000"}):
            with mock.patch.object(launcher, "_port_is_open", side_effect=[False, True]):
                with mock.patch("pathlib.Path.open", log):
                    with mock.patch.object(launcher.subprocess, "Popen", return_value=process):
                        with mock.patch.object(launcher.time, "sleep"):
                            with mock.patch.object(launcher, "run_manage") as run_manage:
                                self.assertIs(launcher.ensure_local_storage(), process)
        run_manage.assert_called_once_with("init_storage")

    def test_failed_initialization_stops_spawned_storage(self):
        process = mock.Mock()
        process.poll.return_value = None
        log = mock.mock_open()
        with mock.patch.dict(os.environ, {"S3_ENDPOINT_URL": "http://localhost:9000"}):
            with mock.patch.object(launcher, "_port_is_open", side_effect=[False, True]):
                with mock.patch("pathlib.Path.open", log):
                    with mock.patch.object(launcher.subprocess, "Popen", return_value=process):
                        with mock.patch.object(launcher.time, "sleep"):
                            with mock.patch.object(
                                launcher, "run_manage", side_effect=RuntimeError("failed")
                            ):
                                with self.assertRaisesRegex(RuntimeError, "failed"):
                                    launcher.ensure_local_storage()
        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=10)

