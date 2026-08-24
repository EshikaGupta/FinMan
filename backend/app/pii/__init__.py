from .redactor import Redactor


def redact(text):

    redactor = Redactor()

    return redactor.redact(text).text