class OpenAIError(Exception):
    """Error rendered in OpenAI's exact wire format, so openai SDKs raise their native exceptions."""

    def __init__(
        self,
        status_code: int,
        message: str,
        error_type: str,
        code: str,
        param: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_type = error_type
        self.code = code
        self.param = param
        self.headers = headers

    def body(self) -> dict[str, object]:
        return {
            "error": {
                "message": self.message,
                "type": self.error_type,
                "param": self.param,
                "code": self.code,
            }
        }


def invalid_api_key(message: str) -> OpenAIError:
    return OpenAIError(401, message, "invalid_request_error", "invalid_api_key")


def admin_required() -> OpenAIError:
    return OpenAIError(
        403,
        "This endpoint requires an admin token.",
        "invalid_request_error",
        "insufficient_permissions",
    )


def model_not_found(model: str) -> OpenAIError:
    return OpenAIError(
        404,
        f"The model '{model}' does not exist or you do not have access to it.",
        "invalid_request_error",
        "model_not_found",
        param="model",
    )


def rate_limit_exceeded(message: str, retry_after_seconds: int) -> OpenAIError:
    return OpenAIError(
        429,
        message,
        "rate_limit_error",
        "rate_limit_exceeded",
        headers={"Retry-After": str(retry_after_seconds)},
    )


def insufficient_quota(message: str) -> OpenAIError:
    return OpenAIError(429, message, "insufficient_quota", "insufficient_quota")
