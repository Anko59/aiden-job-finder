import os
from pathlib import Path
import subprocess
from dataclasses import dataclass
from typing import Any, List, Union
from aiden_app.models import UserProfile, ProfileInfo
from aiden_project.settings import MEDIA_ROOT
from loguru import logger

import fitz  # PyMuPDF
import latexcodec  # noqa: F401
from aiden_project.settings import MEDIA_ROOT
from jinja2 import Environment, FileSystemLoader
from PyPDF2 import PdfReader, PdfWriter

from aiden_app.models import Document, ProfileInfo, UserProfile
from loguru import logger
import tempfile
from django.core.files.base import ContentFile


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

    def generate_cv(self, profile: UserProfile) -> Document:
        template = self.jinja_env.get_template("cv_template.tex")
        info = profile.profile_info.to_json()

        logger.info(f"Generating CV for {profile.user.username}")
        output = self._render_template(template, info)
        logger.info(f"Writing CV as pdf to file for {profile.user.username}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir = Path(tmp_dir)
            document_path = tmp_dir / "cv.tex"
            document_path.write_bytes(output.encode("utf-8"))
            logger.info(f"Compiling CV for {profile.user.username}")
            pdf_path = self._compile_document(document_path)
            logger.info(f"Generating PDF for {profile.user.username}")
            png_path = self._generate_cv_png(pdf_path, tmp_dir / "cv.png")
            # saving cv to db and upload to s3
            logger.info(f"Saving CV for {profile.user.username}")
            # TODO: The pdf is not saved to the database nor in storage, but the png is
            document = Document.objects.create(
                user=profile.user, profile=profile.profile_info, file=ContentFile(png_path.read_bytes(), name="cv.png")
            )

        return document

    def _generate_cv_png(self, pdf_path: Path, png_path: Path):
        doc = fitz.open(pdf_path.as_posix())
        page = doc[0]
        pix = page.get_pixmap()
        pix.save(png_path)
        return png_path

    @classmethod
    def _escape_latex_dict(cls, d: dict | str | list | Any) -> dict:
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

    def _compile_document(self, document_path: Path) -> Path:
        subprocess.run(
            [
                "pdflatex",
                "-interaction=nonstopmode",
                "-output-directory=" + document_path.parent.absolute().as_posix(),
                "-jobname=" + document_path.name.replace(".tex", ""),
                "\\input{" + document_path.absolute().as_posix() + "}",
            ]
        )
        # One aux file, one log and one pdf file should be generated
        pdf = Path(document_path.as_posix().replace(".tex", ".pdf"))
        return pdf

    def _extract_most_content_page(self, document_path: Path):
        """Extract the page with the most content from the PDF"""
        infile = PdfReader(document_path.absolute().as_posix(), "rb")
        max_content_page = max(infile.pages, key=lambda page: len(page.extract_text()))
        output = PdfWriter()
        output.add_page(max_content_page)
        with document_path.open("wb") as f:
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
