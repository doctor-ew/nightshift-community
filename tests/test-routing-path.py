import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'scripts/nightshift-routing-path.py'
spec = importlib.util.spec_from_file_location('routing_path', MODULE)
routing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routing)


class RoutingPathTests(unittest.TestCase):
    def test_project_recovers_without_inherited_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            project = root / 'consumer'
            project.mkdir()
            subprocess.run(['git', 'init', '-q', str(project)], check=True)
            (project / '.nightshift.toml').write_text('[providers]\nrouting_file="custom.json"\n')
            configured = project / 'custom.json'
            configured.write_text('{}')
            child = project / 'docs'
            child.mkdir()
            with patch.dict(os.environ, {}, clear=True):
                result = subprocess.check_output([sys.executable, str(MODULE), str(root)], cwd=child, text=True)
            self.assertEqual(result.strip(), str(configured))
            with patch.dict(os.environ, {'NIGHTSHIFT_PROJECT_DIR': str(project)}, clear=True):
                self.assertEqual(routing.resolve(root), configured)
                configured.rename(project / 'retained.json')
                with self.assertRaises(ValueError):
                    routing.resolve(root)

    def test_explicit_target_beats_server_project_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve(); target=root/'consumer'; target.mkdir()
            (target/'.nightshift.toml').write_text('[providers]\nrouting_file="custom.json"\n')
            configured=target/'custom.json'; configured.write_text('{}')
            with patch.dict(os.environ, {'NIGHTSHIFT_PROJECT_DIR':str(root/'wrong')}, clear=True):
                self.assertEqual(routing.resolve(root, target), configured)

    def test_ticket_worktree_recovers_primary_checkout_routing(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve(); project=root/'project'; project.mkdir()
            subprocess.run(['git','init','-q',str(project)],check=True)
            subprocess.run(['git','-C',str(project),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','--allow-empty','-qm','fixture'],check=True)
            child=root/'child'
            subprocess.run(['git','-C',str(project),'worktree','add','-qb','ticket',str(child)],check=True)
            (project/'.nightshift.toml').write_text('[providers]\nrouting_file="custom.json"\n')
            configured=project/'custom.json'; configured.write_text('{}')
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(routing.resolve(root,child),configured)

    def test_explicit_override_and_install_default(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            default = root / 'routing.json'
            default.write_text('{}')
            override = root / 'override.json'
            override.write_text('{}')
            project = root / 'consumer'
            project.mkdir()
            with patch.dict(os.environ, {'NIGHTSHIFT_PROJECT_DIR': str(project)}, clear=True):
                self.assertEqual(routing.resolve(root), default)
                with patch.dict(os.environ, {'NIGHTSHIFT_ROUTING_FILE': str(override)}):
                    self.assertEqual(routing.resolve(root), override)


if __name__ == '__main__':
    unittest.main()
