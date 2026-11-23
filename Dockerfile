FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY scripts scripts
RUN python scripts/make_icons.py /srv/icons
COPY app app
COPY web web
ENV DB_PATH=/data/app.db ICON_DIR=/srv/icons PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
