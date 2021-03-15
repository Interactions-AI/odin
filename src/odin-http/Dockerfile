FROM python:3.7

COPY . /
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 9003
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9003"]
