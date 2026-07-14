# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv
WORKDIR /build
COPY pyproject.toml ./
COPY src ./src
RUN uv pip install --system ".[ui,dev]"

FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src /app/src
COPY scripts /app/scripts
COPY pyproject.toml /app/
COPY scripts/entrypoint.sh /app/scripts/entrypoint.sh
RUN chmod +x /app/scripts/entrypoint.sh
EXPOSE 8501
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["streamlit", "run", "scripts/backtest_dashboard.py", "--server.address", "0.0.0.0"]