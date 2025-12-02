# core/utils.py

import requests
from django.conf import settings


def send_sms(receiver, message, title="학원 알림"):
    """
    알리고 SMS 발송 함수
    :param receiver: 수신번호 (하이픈 없이, 예: '01012345678')
    :param message: 문자 내용
    :param title: 문자 제목 (LMS 장문 발송 시 사용)
    :return: 성공 여부 (True/False), 메시지
    """
    send_url = 'https://apis.aligo.in/send/'

    sms_data = {
        'key': settings.ALIGO_API_KEY,
        'userid': settings.ALIGO_USER_ID,
        'sender': settings.ALIGO_SENDER,
        'receiver': receiver,
        'msg': message,
        'title': title,
        'msg_type': 'SMS',  # 내용이 길면 자동으로 LMS로 바뀔 수 있음 (알리고 설정에 따라 다름)
    }

    try:
        response = requests.post(send_url, data=sms_data)
        result = response.json()

        # 알리고 응답 코드 확인 (result_code가 1이면 성공)
        if result.get('result_code') == '1':
            return True, "문자 발송 성공"
        else:
            return False, f"발송 실패: {result.get('message')}"

    except Exception as e:
        return False, f"시스템 오류: {str(e)}"