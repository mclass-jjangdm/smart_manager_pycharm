# 최신 Python 이미지를 기반으로 함
FROM python:3.12

# 환경 변수 설정
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# mysqlclient 빌드에 필요한 C 컴파일러 및 MariaDB 개발 라이브러리 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    libmariadb-dev

# Django와 MariaDB 연결 드라이버 등 설치
RUN pip install django gunicorn mysqlclient pandas openpyxl reportlab requests

# /app 폴더를 작업 디렉토리로 설정
WORKDIR /app