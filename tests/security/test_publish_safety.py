import subprocess

from scripts.check_publish import private_tracked_files


def test_publish_check_detects_tracked_private_data_even_if_ignored(tmp_path):
    subprocess.run(['git', 'init', str(tmp_path)], check=True, capture_output=True)
    (tmp_path / 'data').mkdir()
    (tmp_path / 'data/private.json').write_text('{}')
    (tmp_path / '.gitignore').write_text('data/\n')
    subprocess.run(['git', '-C', str(tmp_path), 'add', '-f', 'data/private.json'], check=True)
    assert private_tracked_files(tmp_path) == ['data/private.json']


def test_publish_check_allows_source_and_env_example(tmp_path):
    subprocess.run(['git', 'init', str(tmp_path)], check=True, capture_output=True)
    (tmp_path / 'main.py').write_text('print("example")')
    (tmp_path / '.env.example').write_text('PASSWORD=')
    subprocess.run(['git', '-C', str(tmp_path), 'add', 'main.py', '.env.example'], check=True)
    assert private_tracked_files(tmp_path) == []


def test_publish_check_detects_force_added_certificate(tmp_path):
    subprocess.run(['git', 'init', str(tmp_path)], check=True, capture_output=True)
    (tmp_path / 'certificate.p12').write_bytes(b'private certificate')
    (tmp_path / '.gitignore').write_text('*.p12\n')
    subprocess.run(['git', '-C', str(tmp_path), 'add', '-f', 'certificate.p12'], check=True)
    assert private_tracked_files(tmp_path) == ['certificate.p12']
