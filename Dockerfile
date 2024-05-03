FROM python:3.9.2

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip==23.3.2 && pip install --no-cache-dir --progress-bar off -r requirements.txt

COPY . .

EXPOSE 8000

CMD python manage.py runserver 0.0.0.0:8000
