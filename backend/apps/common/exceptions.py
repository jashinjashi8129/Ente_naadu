import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework.exceptions import (
    APIException,
    ValidationError,
    PermissionDenied,
    NotAuthenticated,
    AuthenticationFailed,
    NotFound
)

logger = logging.getLogger(__name__)

def _format_error_detail(detail):
    """
    Extracts a human-readable single string from nested DRF error details.
    """
    if isinstance(detail, list):
        if detail:
            return _format_error_detail(detail[0])
        return "അസാധുവായ വിവരങ്ങൾ."
    elif isinstance(detail, dict):
        # Extract first field's error
        for field, err in detail.items():
            field_name = field if field != 'non_field_errors' else ''
            err_msg = _format_error_detail(err)
            return f"{field_name}: {err_msg}".strip(": ") if field_name else err_msg
        return "അസാധുവായ വിവരങ്ങൾ."
    return str(detail)

def custom_exception_handler(exc, context):
    """
    Unified DRF Exception Handler for Ente Naadu:
    - Provides consistent response payload for Web & Flutter Mobile.
    - Preserves standard 'detail' field for backward compatibility.
    - Adds 'error', 'code', 'errors', and 'status_code' for reliable client parsing.
    """
    # Call REST framework's default exception handler first to get the standard response
    response = exception_handler(exc, context)

    if response is not None:
        view = context.get('view', None)
        view_name = view.__class__.__name__ if view else 'UnknownView'

        # Determine error code
        code = getattr(exc, 'default_code', 'ERROR').upper()
        if isinstance(exc, ValidationError):
            code = 'VALIDATION_ERROR'
        elif isinstance(exc, (PermissionDenied, DjangoPermissionDenied)):
            code = 'PERMISSION_DENIED'
        elif isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
            code = 'AUTHENTICATION_REQUIRED'
        elif isinstance(exc, (NotFound, Http404)):
            code = 'NOT_FOUND'

        primary_message = _format_error_detail(response.data)

        # Standardized envelope
        response.data = {
            "success": False,
            "error": primary_message,
            "detail": primary_message,  # Ensure mobile apps reading 'detail' get clean text
            "error_code": code,
            "errors": response.data if isinstance(response.data, dict) else {"detail": response.data},
            "status_code": response.status_code
        }
        return response

    # Unhandled exceptions (500 Internal Server Errors)
    logger.exception(f"Unhandled exception in API view {context.get('view')}: {exc}", exc_info=exc)

    if settings.DEBUG:
        # In debug mode, allow Django default debugging trace
        return None

    return Response({
        "success": False,
        "error": "സെർവറിൽ ഒരു സാങ്കേതിക തകരാർ നേരിട്ടു. ദയവായി അല്പം കഴിഞ്ഞ് വീണ്ടും ശ്രമിക്കുക.",
        "detail": "An internal server error occurred. Please try again later.",
        "error_code": "INTERNAL_SERVER_ERROR",
        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
