from .tool import Tool
from .utils.cv_editor import CVEdit, CVEditor


class CVEditorTool(Tool):
    def __init__(self, profile):
        self.profile = profile
        self.cv_editor = CVEditor()
        super().__init__("CVEditor")
        self.add_tool("edit_user_profile", self.edit_user_profile)

    @Tool.tool_function
    def edit_user_profile(self, new_profile_name: str, edits: list):
        cv_edits = [CVEdit(path=edit["path"], operation=edit["operation"], value=edit["value"]) for edit in edits]
        new_profile, edition_errors = self.cv_editor.edit_profile(self.profile, new_profile_name, cv_edits)

        pdf_path = self.cv_editor.generate_cv(new_profile)
        return {
            "status": "success",
            "errors": edition_errors,
            "document_path": pdf_path,
        }
