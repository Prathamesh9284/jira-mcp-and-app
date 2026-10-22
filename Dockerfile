FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app_api/ ./app_api/
COPY jira_timelog/ ./jira_timelog/

EXPOSE 8000

CMD ["uvicorn", "app_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
