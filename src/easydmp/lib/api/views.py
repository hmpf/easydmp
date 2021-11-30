from rest_framework import serializers
from rest_framework import exceptions
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)

    if response is None:
        return response

    if isinstance(exc, serializers.ValidationError):
        if isinstance(response.data, dict):
            errors = []
            for key, value in response.data.items():
                errors.append({'field': key, 'message': value})
            response.data = {
                'category': 'input_validation',
                'field-errors': errors,
            }
        elif isinstance(response.data, list):
            errors = []
            for item in response.data:
                errors.append({'category': item.code, 'message': str(item)})
            response.data = {
                'errors': errors,
            }
        else:
            return response
        response.data['status_code'] = response.status_code
    elif isinstance(exc, exceptions.APIException):
        response.data = {'category': exc.get_codes(), 'message': exc.detail}
        response.data['status_code'] = exc.status_code
    return response
