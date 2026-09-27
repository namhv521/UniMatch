"""
Basic structure tests for KLTN project.
Validates repository layout and prerequisites for KLTN-DAY-01.
"""

from pathlib import Path


def test_repo_structure():
    """Verify essential directories exist."""
    repo_root = Path(__file__).parent.parent
    
    required_dirs = [
        "data",
        "docs",
        "tests",
    ]
    
    for dir_name in required_dirs:
        dir_path = repo_root / dir_name
        assert dir_path.exists(), f"Missing directory: {dir_name}"
        assert dir_path.is_dir(), f"{dir_name} is not a directory"


def test_documentation_exists():
    """Verify architecture notes are created."""
    repo_root = Path(__file__).parent.parent
    arch_file = repo_root / "docs" / "KIEN_TRUC.md"
    
    assert arch_file.exists(), "Architecture notes (KIEN_TRUC.md) not found"
    assert arch_file.stat().st_size > 0, "Architecture notes file is empty"


def test_git_initialized():
    """Verify repository is Git-initialized."""
    repo_root = Path(__file__).parent.parent
    git_dir = repo_root / ".git"
    
    assert git_dir.exists(), ".git directory not found"
    assert git_dir.is_dir(), ".git is not a directory"


def test_pyproject_exists():
    """Verify pyproject.toml is configured."""
    repo_root = Path(__file__).parent.parent
    pyproject_file = repo_root / "pyproject.toml"
    
    assert pyproject_file.exists(), "pyproject.toml not found"
    assert pyproject_file.stat().st_size > 0, "pyproject.toml is empty"


def test_readme_exists():
    """Verify project README exists."""
    repo_root = Path(__file__).parent.parent
    readme_file = repo_root / "README.md"
    
    assert readme_file.exists(), "README.md not found"
    assert readme_file.stat().st_size > 0, "README.md is empty"


if __name__ == "__main__":
    test_repo_structure()
    test_documentation_exists()
    test_git_initialized()
    test_pyproject_exists()
    test_readme_exists()
    print("✅ All structure tests passed!")
