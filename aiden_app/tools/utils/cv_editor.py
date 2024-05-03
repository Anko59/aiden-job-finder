import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any, List, Union

import fitz  # PyMuPDF, imported as fitz for backward compatibility reasons
from jinja2 import Environment, FileSystemLoader
from PyPDF2 import PdfReader, PdfWriter


@dataclass
class CVEdit:
    path: List[Union[str, int]]
    operation: str
    value: Union[str, dict, Any]


class CVEditor:
    def __init__(self, first_name: str, last_name: str):
        self.user_data_dir = os.path.join(os.path.dirname(__file__), '../../user_data/')
        self.static_image_dir = os.path.join(
            os.path.dirname(__file__),
            '../../static/images/user_images/cv',
        )
        self.env = Environment(
            loader=FileSystemLoader(self.user_data_dir),
            comment_start_string='[èà_',
            comment_end_string='"àé"()',
        )
        self.first_name = first_name
        self.last_name = last_name
        self.user_dir = self._create_user_directory()

    def generate_cv(self, cv_title: str, profile_content_file: str = 'default_profile'):
        template = self._load_template('cv_template.tex')
        info = self._load_json_file(self.user_dir, profile_content_file)
        if 'photo_url' in info:
            info['photo_url'] = os.path.join(self.static_image_dir, info['photo_url'])
        output = self._render_template(template, info)
        document_path = self._write_to_file(output, self.user_dir, f'CV_{self.first_name}_{self.last_name}_{cv_title}')
        self._compile_document(document_path)
        self._extract_most_content_page(document_path)
        self._clean_user_directory()
        pdf_path = document_path.replace('.tex', '.pdf')
        self._generate_cv_png(
            pdf_path,
            os.path.join(
                self.static_image_dir,
                f'cv_{self.first_name}_{self.last_name}_{cv_title}.png',
            ),
        )
        return pdf_path

    def _generate_cv_png(self, pdf_path: str, png_path: str):
        doc = fitz.open(pdf_path)
        page = doc[0]
        pix = page.get_pixmap()
        pix.save(png_path)

    def _clean_user_directory(self):
        for file in os.listdir(self.user_dir):
            if file.endswith('.aux') or file.endswith('.log') or file.endswith('.tex') or file.endswith('.out'):
                os.remove(os.path.join(self.user_dir, file))

    def _create_user_directory(self) -> str:
        directory_name = f'{self.first_name.lower()}_{self.last_name.lower()}'
        user_dir = os.path.join(self.user_data_dir, directory_name)
        os.makedirs(user_dir, exist_ok=True)
        return user_dir

    def _load_template(self, template_name: str) -> Any:
        return self.env.get_template(template_name)

    def _load_json_file(self, dir: str, file_name: str) -> dict:
        with open(os.path.join(dir, f'{file_name}.json'), 'r') as f:
            return json.load(f)

    def _render_template(self, template: Any, info: dict) -> str:
        output = template.render(**info)
        return '\n'.join([x.replace('{ ', '{').replace(' }', '}') for x in output.split('\n') if x])

    def _write_to_file(self, content: str, dir: str, file_name: str, ext='.tex') -> str:
        document_path = os.path.join(dir, f'{file_name}{ext}')
        with open(document_path, 'w') as f:
            f.write(content)
        return document_path

    def _compile_document(self, document_path: str):
        subprocess.run(
            [
                'pdflatex',
                '-interaction=nonstopmode',
                '-output-directory=' + os.path.dirname(document_path),
                '-jobname=' + os.path.basename(document_path).replace('.tex', ''),
                '\\input{' + document_path + '}',
            ]
        )
        for file in os.listdir(os.path.dirname(document_path)):
            if file.endswith('.aux') or file.endswith('.log'):
                os.remove(os.path.join(os.path.dirname(document_path), file))

    def _extract_most_content_page(self, document_path: str):
        infile = PdfReader(document_path.replace('.tex', '.pdf'), 'rb')
        max_content_page = max(infile.pages, key=lambda page: len(page.extract_text()))
        output = PdfWriter()
        output.add_page(max_content_page)
        with open(document_path.replace('.tex', '.pdf'), 'wb') as f:
            output.write(f)

    def edit_profile(self, base_profile: str, new_profile_name: str, edits: List[CVEdit]):
        base_profile = self._load_json_file(self.user_dir, base_profile)

        for edit in edits:
            element = base_profile
            try:
                for path_element in edit.path[:-1]:
                    element = element[path_element]
                if edit.operation == 'delete':
                    del element[edit.path[-1]]
                elif edit.operation == 'insert':
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
                yield {'error': str(e)}

        self._write_to_file(json.dumps(base_profile, indent=4), self.user_dir, new_profile_name, '.json')

    def list_files(self, extension: str) -> List[str]:
        return [file.replace(extension, '') for file in os.listdir(self.user_dir) if file.endswith(extension)]

    def list_profiles(self) -> List[str]:
        return self.list_files('.json')

    def list_cvs(self) -> List[str]:
        return self.list_files('.pdf')

    def get_profile(self, profile_name: str) -> dict:
        return self._load_json_file(self.user_dir, profile_name)
