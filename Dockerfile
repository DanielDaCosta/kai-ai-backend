FROM python:3.10.12

WORKDIR /code

COPY requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir -r /code/requirements.txt

COPY ./app /code/app 

# Local development key set
# ENV TYPES: dev, production
# When set to dev, API Key on endpoint requests are just 'dev'
# When set to production, API Key on endpoint requests are the actual API Key


ENV GOOGLE_APPLICATION_CREDENTIALS=/app/local-auth.json 
ENV ENV_TYPE="dev"
ENV PROJECT_ID="heroic-climber-423918-r1"

ENV PYTHONPATH=/app


CMD ["fastapi", "dev", "app/main.py", "--host=0.0.0.0", "--port=8000"]
