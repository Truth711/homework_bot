class BaseError(Exception):
    """Базовый класс ошибок."""
    pass


class SendMessageError(BaseError):
    """Не удалось отправить сообщение."""
    pass


class UnexpectedStatusCodeError(BaseError):
    """Ответ API содержит статус код, отличный от 200."""
    pass


class ExpectedKeysNotFoundError(BaseError):
    """Отсутствие ожидаемых ключей в ответе API."""
    pass


class UnexpectedStatusError(BaseError):
    """Обнаружен недокументированный статус домашней работы в ответе API."""
    pass
