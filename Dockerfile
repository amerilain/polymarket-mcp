FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml polymarket_mcp.py ./

RUN pip install --no-cache-dir -e .

EXPOSE 8000

ENTRYPOINT ["polymarket-mcp"]
CMD ["--http", "8000"]
