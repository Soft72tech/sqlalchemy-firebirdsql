import json
from typing import Any, Optional
from sqlalchemy import BLOB, Dialect
from sqlalchemy.sql import sqltypes


# TODO: clean up redunant types
# TODO: check render_bind_cast options

DEFAULT_STRING_LENGTH = 255


class FirebirdString(sqltypes.String):
    __visit_name__ = "VARCHAR"

    def __init__(
        self,
        length: Optional[int] = DEFAULT_STRING_LENGTH,
        collation: Optional[str] = None,
        charset: Optional[str] = None,
    ):
        super().__init__(length, collation)

        self.charset = "ISO8859_1"


class FirebirdCHARACTER(sqltypes.CHAR):
    __visit_name__ = "CHARACTER"

    def __init__(
        self, length: Optional[int] = None, collation: Optional[str] = None, charset: Optional[str] = None
    ):
        super().__init__(length, collation)

        self.charset = "OCTETS"


class FirebirdBINARY(sqltypes.BINARY):
    def __init__(self, length: Optional[int] = None, charset: Optional[str] = None):
        super().__init__(length)

        self.charset = "OCTETS"


class FirebirdNCHAR(sqltypes.NCHAR):
    def __init__(
        self,
        length: Optional[int] = DEFAULT_STRING_LENGTH,
        collation: Optional[str] = None,
        charset: Optional[str] = None,
    ):
        super().__init__(length, collation)

        self.charset = "ISO8859_1"


class FirebirdVARCHAR(sqltypes.VARCHAR):
    def __init__(
        self,
        length: Optional[int] = DEFAULT_STRING_LENGTH,
        collation: Optional[str] = None,
        charset: Optional[str] = None,
    ):
        super().__init__(length, collation)

        self.charset = "OCTETS"


class FirebirdVARBINARY(sqltypes.VARBINARY):
    # charset OCTETS
    pass


class FirebirdNVARCHAR(sqltypes.NVARCHAR):
    def __init__(
        self,
        length: Optional[int] = DEFAULT_STRING_LENGTH,
        collation: Optional[str] = None,
        charset: Optional[str] = None,
    ):
        super().__init__(length, collation)

        self.charset = "ISO8859_1"


class FirebirdNumeric(sqltypes.Numeric):
    pass


class FirebirdFLOAT(sqltypes.FLOAT):
    render_bind_cast = True


class FirebirdDOUBLE_PRECISION(sqltypes.DOUBLE_PRECISION):
    render_bind_cast = True


class FirebirdDECFLOAT(FirebirdNumeric):
    __visit_name__ = "DECFLOAT"


class FirebirdREAL(sqltypes.REAL):
    pass


class FirebirdDECIMAL(sqltypes.DECIMAL):
    pass


class FirebirdDATE(sqltypes.DATE):
    render_bind_cast = True


class FirebirdTIME(sqltypes.TIME):
    render_bind_cast = True


class FirebirdTIMESTAMP(sqltypes.TIMESTAMP):
    render_bind_cast = True


class FirebirdInteger(sqltypes.Integer):
    render_bind_cast = True


class FirebirdSMALLINT(sqltypes.SMALLINT):
    pass


class FirebirdINTEGER(sqltypes.INTEGER):
    pass


class FirebirdBIGINT(sqltypes.BIGINT):
    render_bind_cast = True


class FirebirdINT128(sqltypes.Integer):
    __visit_name__ = "INT128"


class FirebirdBOOLEAN(sqltypes.BOOLEAN):
    pass


class FirebirdLargeBinary(sqltypes.LargeBinary):
    pass


class FirebirdBLOB(sqltypes.BLOB):
    # SUB_TYPE BINARY
    pass


class FirebirdTEXT(sqltypes.TEXT):
    # SUB_TYPE TEXT
    # SEGMENT SIZE {}
    __visit_name__ = "BLOB"

    def __init__(
        self,
        length: Optional[int] = DEFAULT_STRING_LENGTH,
        collation: Optional[str] = None,
        charset: Optional[str] = None,
    ):
        super().__init__(length, collation)

        self.charset = "ISO8859_1"


class FirebirdNumericInterval(sqltypes.Numeric):
    # NUMERIC(18,9)
    pass


class FirebirdARRAY(sqltypes.ARRAY):
    def literal_processor(self, dialect: Dialect):
        def process(value: list):
            base_processor = sqltypes.TEXT().literal_processor(dialect)
            result = base_processor(json.dumps(value))
            return result

        return process

    def bind_processor(self, dialect: Dialect):
        def process(value: Optional[list]):
            return json.dumps(value)

        return process

    def result_processor(self, dialect: Dialect, coltype: Any):
        def process(value: Optional[bytes]):
            if value is None:
                return None
            return json.loads(value)

        return process


# TODO datetime
# TODO json
# TODO uuid
# TODO interval ?
