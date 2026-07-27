# Backend-only image. The frontend (frontend/app.py) is meant to run on
# Streamlit Community Cloud instead (free, and it's what Streamlit Cloud
# expects — a Dockerfile there would be redundant). See DEPLOY.md.

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render/Railway/Fly inject $PORT at runtime; default to 8000 for local `docker run`.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
