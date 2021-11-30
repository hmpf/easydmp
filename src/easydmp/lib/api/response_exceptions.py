from rest_framework.exceptions import APIException


class DRFIntegrityError(APIException):  # 409 Conflict
    status_code = 409
    default_detail = 'Could not save changes.'
    default_code = 'database_integrity'


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = 'Service temporarily unavailable, try again later.'
    default_code = 'service_unavailable'
