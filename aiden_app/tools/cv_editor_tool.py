import functools
import json

from .tool import Tool
from .utils.cv_editor import CVEdit, CVEditor


class CVEditorTool(Tool):
    def __init__(self, **kwargs):
        self.cv_editor = CVEditor(**kwargs)
        self.name = 'cvEditorTool'

    @property
    def names_to_functions(self):
        return {
            'edit_user_profile': functools.partial(self.edit_user_profile),
        }

    def generate_cv(self, cv_title: str, profile_content_file: str = 'profile_content'):
        try:
            self.cv_editor.generate_cv(cv_title, profile_content_file)
            return json.dumps({'status': 'success'})
        except Exception as e:
            return json.dumps({'error': str(e)})

    def edit_profile(self, base_profile: str, new_profile_name: str, edits: list):
        try:
            edition_errors = []
            cv_edits = [CVEdit(path=edit['path'], operation=edit['operation'], value=edit['value']) for edit in edits]
            for error in self.cv_editor.edit_profile(base_profile, new_profile_name, cv_edits):
                edition_errors.append(error)
            return json.dumps({'status': 'success', 'errors': edition_errors})
        except Exception as e:
            return json.dumps({'status': 'error', 'errors': [str(e)]})

    def list_profiles(self):
        try:
            return json.dumps(self.cv_editor.list_profiles())
        except Exception as e:
            return json.dumps({'error': str(e)})

    def get_profile(self, profile_name: str):
        try:
            return json.dumps(self.cv_editor.get_profile(profile_name))
        except Exception as e:
            return json.dumps({'error': str(e)})

    def list_cvs(self):
        try:
            return json.dumps(self.cv_editor.list_cvs())
        except Exception as e:
            return json.dumps({'error': str(e)})

    def read_user_profile(self):
        try:
            return json.dumps(self.cv_editor.get_profile('default_profile'))
        except Exception as e:
            return json.dumps({'error': str(e)})

    def edit_user_profile(self, new_profile_name: str, edits: list):
        edition_errors = []
        try:
            cv_edits = [CVEdit(path=edit['path'], operation=edit['operation'], value=edit['value']) for edit in edits]
            for error in self.cv_editor.edit_profile('default_profile', new_profile_name, cv_edits):
                edition_errors.append(error)
            pdf_path = self.cv_editor.generate_cv(new_profile_name, new_profile_name)
            return json.dumps(
                {
                    'status': 'success',
                    'errors': edition_errors,
                    'document_path': pdf_path,
                }
            )
        except Exception as e:
            return json.dumps({'status': 'error', 'errors': [str(e)] + edition_errors})
