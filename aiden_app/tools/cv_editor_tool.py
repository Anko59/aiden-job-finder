from .tool import Tool
from .utils.cv_editor import CVEdit, CVEditor


class CVEditorTool(Tool):
    def __init__(self, **kwargs):
        self.cv_editor = CVEditor(**kwargs)
        super().__init__("CVEditor")
        self.add_tool("edit_user_profile", self.edit_user_profile)

    @Tool.tool_function
    def edit_user_profile(self, new_profile_name: str, edits: list):
        edition_errors = []
        cv_edits = [CVEdit(path=edit["path"], operation=edit["operation"], value=edit["value"]) for edit in edits]
        for error in self.cv_editor.edit_profile("default_profile", new_profile_name, cv_edits):
            edition_errors.append(error)
        pdf_path = self.cv_editor.generate_cv(new_profile_name, new_profile_name)
        return {
            "status": "success",
            "errors": edition_errors,
            "document_path": pdf_path,
        }
