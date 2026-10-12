FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir --no-deps .
COPY data ./data
COPY models ./models
COPY reports ./reports
EXPOSE 8000
CMD ["python", "-m", "wattscope.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]
