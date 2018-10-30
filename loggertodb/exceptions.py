class LoggerToDbError(Exception):
    pass


class MeteologgerStorageReadError(LoggerToDbError):
    pass


class ConfigurationError(LoggerToDbError):
    pass
