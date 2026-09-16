# Backend-only image. The frontend (frontend/app.py) is meant to run on
# Streamlit Community Cloud instead (free, and it's what Streamlit Cloud
# expects — a Dockerfile there would be redundant). See DEPLOY.md.

FROM python:3.12-slim

WORKDIR /app

# requirements-backend.txt (not requirements.txt) -- the latter also covers
# frontend/app.py (Streamlit) and pulls in streamlit/pandas/numpy/pyarrow/
# etc., none of which api/, app/, services/, agents/, models/, or utils/
# import. Keeping this image to just what the backend actually uses saves
# ~500MB and a chunk of cold-deploy time on a free host.
COPY requirements-backend.txt .
RUN pip install --no-cache-dir -r requirements-backend.txt

COPY . .

# Run as an unprivileged user -- an RCE-class bug in a dependency (uvicorn,
# pypdf, requests, ...) then lands as a normal user inside the container
# instead of root.
RUN useradd --create-home --uid 1000 appuser
USER appuser

# Render/Railway/Fly inject $PORT at runtime; default to 8000 for local `docker run`.
ENV PORT=8000
EXPOSE 8000

# --forwarded-allow-ips is what makes the rate limiter work at all on a
# hosted deployment. Every request arrives through the platform's proxy, so
# without it request.client.host is that proxy for EVERY visitor -- the
# per-IP limiter then shares one 20-requests-per-minute bucket across the
# entire user base, and a handful of people interviewing at once start
# throttling each other. uvicorn ignores X-Forwarded-For unless the
# immediate peer is trusted, and it trusts only 127.0.0.1 by default.
#
# "*" is safe specifically because the container is not publicly routable:
# the platform's proxy is the only thing that can reach it, so the header
# cannot be spoofed by a client. On a host where the app is directly
# reachable this must be the proxy's real address instead.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
