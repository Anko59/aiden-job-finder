import os
import subprocess
from dataclasses import dataclass
from typing import Any, List, Union
from urllib.parse import unquote

import fitz  # PyMuPDF
import latexcodec  # noqa: F401
from aiden_project.settings import MEDIA_ROOT
from jinja2 import Environment, FileSystemLoader
from PyPDF2 import PdfReader, PdfWriter

from aiden_app.models import ProfileInfo, UserProfile


@dataclass
class CVEdit:
    path: List[Union[str, int]]
    operation: str
    value: Union[str, dict, Any]


class CVEditor:
    def __init__(self):
        self.cv_images_path = os.path.join(MEDIA_ROOT, "cv")
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.cv_images_path),
            # Due to many compilers having different comment delimiters,
            # we cannot have comments in the template
            comment_start_string="[èà_",
            comment_end_string='"àé"()',
        )

    def generate_cv(self, profile: UserProfile):
        template = self.jinja_env.get_template("cv_template.tex")
        info = profile.profile_info.to_json()
        info["photo_url"] = "../profile/" + unquote(profile.photo.url.split("/")[-1])

        output = self._render_template(template, info)
        document_path = self._write_to_file(output, profile.cv_path.replace(".pdf", ".tex"))
        self._compile_document(document_path)
        self._extract_most_content_page(document_path)
        self._clean_user_directory()
        pdf_path = document_path.replace(".tex", ".pdf")
        png_path = pdf_path.replace(".pdf", ".png")
        self._generate_cv_png(pdf_path, png_path)
        return pdf_path

    def _clean_user_directory(self):
        for file in os.listdir(self.cv_images_path):
            if file.endswith(".aux") or file.endswith(".log") or file.endswith(".tex") or file.endswith(".out"):
                if file != "cv_template.tex":
                    os.remove(os.path.join(self.cv_images_path, file))

    def _generate_cv_png(self, pdf_path: str, png_path: str):
        doc = fitz.open(pdf_path)
        page = doc[0]
        pix = page.get_pixmap()
        pix.save(png_path)

    @classmethod
    def _escape_latex_dict(cls, d: dict) -> dict:
        # Clean up the dictionary to escape LaTeX special characters
        if isinstance(d, dict):
            return {k: cls._escape_latex_dict(v) for k, v in d.items()}
        elif isinstance(d, list):
            return [cls._escape_latex_dict(i) for i in d]
        elif isinstance(d, str):
            return d.encode("latex").decode("utf-8")
        else:
            return d

    def _render_template(self, template: Any, info: dict) -> str:
        info = self._escape_latex_dict(info)
        output = template.render(**info)
        return "\n".join([x.replace("{ ", "{").replace(" }", "}") for x in output.split("\n") if x])

    def _write_to_file(self, content: str, document_path: str) -> str:
        with open(document_path, "w") as f:
            f.write(content)
        return document_path

    def _compile_document(self, document_path: str):
        subprocess.run(
            [
                "pdflatex",
                "-interaction=nonstopmode",
                "-output-directory=" + os.path.dirname(document_path),
                "-jobname=" + os.path.basename(document_path).replace(".tex", ""),
                "\\input{" + document_path + "}",
            ]
        )
        for file in os.listdir(os.path.dirname(document_path)):
            if file.endswith(".aux") or file.endswith(".log"):
                os.remove(os.path.join(os.path.dirname(document_path), file))

    def _extract_most_content_page(self, document_path: str):
        infile = PdfReader(document_path.replace(".tex", ".pdf"), "rb")
        max_content_page = max(infile.pages, key=lambda page: len(page.extract_text()))
        output = PdfWriter()
        output.add_page(max_content_page)
        with open(document_path.replace(".tex", ".pdf"), "wb") as f:
            output.write(f)

    def edit_profile(
        self,
        base_profile: UserProfile,
        new_profile_name: str,
        edits: List[CVEdit],
    ) -> tuple[UserProfile, list[dict]]:
        profile_info = base_profile.profile_info.to_json()
        errors = []
        for edit in edits:
            element = profile_info
            try:
                for path_element in edit.path[:-1]:
                    element = element[path_element]
                if edit.operation == "delete":
                    del element[edit.path[-1]]
                elif edit.operation == "insert":
                    if isinstance(element[edit.path[-1]], list):
                        if isinstance(edit.value, list):
                            element[edit.path[-1]] += edit.value
                        else:
                            element[edit.path[-1]].append(edit.value)

                    elif isinstance(element[edit.path[-1]], dict):
                        element[edit.path[-1]] = {
                            **element[edit.path[-1]],
                            **edit.value,
                        }

                else:
                    element[edit.path[-1]] = edit.value
            except Exception as e:
                errors.append({"error": str(e)})
        profile_info = ProfileInfo.from_json(profile_info, user=base_profile.user)
        new_profile = UserProfile.objects.create(
            first_name=base_profile.first_name,
            last_name=base_profile.last_name,
            profile_title=new_profile_name,
            profile_info=profile_info,
            photo=base_profile.photo,
            user=base_profile.user,
        )
        new_profile.save()

        return new_profile, errors
