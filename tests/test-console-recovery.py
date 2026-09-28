#!/usr/bin/env python3
"""CLI/browser recovery share the controller and preserve explicit authorization."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('actions', ROOT/'scripts/nightshift-console-actions.py')
actions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actions)


class RecoveryActions(unittest.TestCase):
    def test_browser_assessment_has_no_authorization(self):
        controller = Mock()
        with patch.object(actions, 'state', return_value={'sha256': 'settings'}), patch.object(actions._recovery, 'load', return_value=controller):
            actions.recovery_action('/fixture', 'sample', 'settings', 'recovery-assess')
        controller.operate.assert_called_once_with('/fixture', 'sample', 'assess')

    def test_authorize_and_resume_forward_exact_binding_and_identity(self):
        for operation in ('authorize', 'resume'):
            controller = Mock()
            with patch.object(actions, 'state', return_value={'sha256': 'settings'}), patch.object(actions._recovery, 'load', return_value=controller):
                actions.recovery_action('/fixture', 'sample', 'settings', 'recovery-'+operation, 'exact-evidence', 'operator')
            controller.operate.assert_called_once_with('/fixture', 'sample', operation, 'exact-evidence', 'operator')

    def test_changed_settings_block_before_controller(self):
        with patch.object(actions, 'state', return_value={'sha256': 'new'}), patch.object(actions._recovery, 'load') as load:
            with self.assertRaisesRegex(ValueError, 'settings changed'):
                actions.recovery_action('/fixture', 'sample', 'old', 'recovery-authorize', 'old-evidence', 'operator')
        load.assert_not_called()

    def test_unknown_operation_cannot_reach_controller(self):
        controller = Mock()
        with patch.object(actions, 'state', return_value={'sha256': 'settings'}), patch.object(actions._recovery, 'load', return_value=controller):
            with self.assertRaisesRegex(ValueError, 'Invalid recovery'):
                actions.recovery_action('/fixture', 'sample', 'settings', 'recover-anything')
        controller.operate.assert_not_called()


if __name__ == '__main__':
    unittest.main()
