"""Resource limits must fail closed before creating cloud resources."""

import contextlib
import io
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from daytona.common.errors import DaytonaNotFoundError

from infra.daytona import manage


class ResourceLimitTests(unittest.TestCase):
    def test_existing_workspace_is_reused(self):
        api = MagicMock()
        api.get.return_value = SimpleNamespace(id="ours", name="workspace", labels={"vision.owner": manage.OWNER})
        with contextlib.redirect_stdout(io.StringIO()), patch.object(manage, "recorded", return_value={"id": "ours", "name": "workspace"}):
            manage.provision(api)
        api.create.assert_not_called()
        api.volume.get.assert_not_called()

    def test_other_project_worker_blocks_new_workspace(self):
        api = MagicMock()
        api.get.side_effect = DaytonaNotFoundError("Not found")
        api.list.return_value = [SimpleNamespace(name="old-benchmark-worker")]
        with self.assertRaisesRegex(RuntimeError, "sandbox limit"):
            manage.provision(api)
        api.create.assert_not_called()
        api.volume.get.assert_not_called()

    def test_snapshot_limit_does_not_create_alternate_name(self):
        api = MagicMock()
        api.snapshot.get.side_effect = [DaytonaNotFoundError("Not found"), SimpleNamespace(id="ours")]
        with patch.object(manage, "recorded", return_value={"id": "ours"}), self.assertRaisesRegex(RuntimeError, "snapshot limit"):
            manage.build(api)
        api.snapshot.create.assert_not_called()

    def test_existing_snapshot_is_reused(self):
        api = MagicMock()
        api.snapshot.get.return_value = SimpleNamespace(id="ours", name="vision-workspace-runtime", state="active")
        with contextlib.redirect_stdout(io.StringIO()), patch.object(manage, "recorded", return_value={"id": "ours", "name": "vision-workspace-runtime"}):
            manage.build(api)
        api.snapshot.create.assert_not_called()

    def test_continuous_workspace_requires_volume(self):
        api = MagicMock()
        with self.assertRaisesRegex(ValueError, "persistent volume"):
            manage.provision(api, without_volume=True)
        api.create.assert_not_called()

    def test_matching_label_with_different_id_is_rejected(self):
        api = MagicMock()
        api.get.return_value = SimpleNamespace(id="someone-else", name="workspace", labels={"vision.owner": manage.OWNER})
        with patch.object(manage, "recorded", return_value={"id": "ours", "name": "workspace"}), self.assertRaisesRegex(ValueError, "recorded ID"):
            manage.owned(api)


if __name__ == "__main__":
    unittest.main()
