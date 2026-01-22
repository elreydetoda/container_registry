FROM itsafeaturemythic/mythic_python_base:latest as builder

COPY ["requirements.txt", "requirements.txt"]
RUN python3 -m pip wheel --wheel-dir /wheels -r requirements.txt

FROM python:3.11-slim

# Install skopeo and other dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    skopeo \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
RUN pip install --no-cache /wheels/*

WORKDIR /Mythic/

COPY [".", "."]

CMD ["python3", "main.py"]