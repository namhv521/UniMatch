"""Explicit opt-in factory; never changes or falls back to the incumbent API."""
import json
import os
from pathlib import Path

from backend.app.rebuild_assistant_api import create_app as create_base_app
from src.serving.github_service import GithubAssistant, load_github_service


def create_app(*, bundle_path=None,selection_path=None,runtime_dir=None,service=None,
               assistant=None,token=None,frontend_dir=None,allow_origins=None):
    if service is None:
        bundle_path=bundle_path or os.environ.get('UNIMATCH_GITHUB_BUNDLE')
        selection_path=selection_path or os.environ.get('UNIMATCH_GITHUB_SELECTION')
        if not bundle_path or not selection_path:
            raise ValueError('explicit_github_bundle_and_selection_required')
        runtime_dir=runtime_dir or os.environ.get('UNIMATCH_GITHUB_RUNTIME') or Path(__file__).resolve().parents[2]/'data_rebuild/v1/runtime/github'
        service=load_github_service(bundle_path,selection_path,runtime_dir)
    if assistant is None:
        source=service.github_serving
        assistant=GithubAssistant(json.loads(Path(source['source_profiles_path']).read_bytes()),service,
            github_run=source['github_source_run'],github_manifest_sha256=source['github_manifest_sha256'],
            quality_review_path=source['github_quality_review_path'],
            quality_review_sha256=source['github_quality_review_sha256'])
    app = create_base_app(service=service,assistant=assistant,token=token,
                          frontend_dir=frontend_dir,allow_origins=allow_origins)
    return app
