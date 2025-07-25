from sqlalchemy.sql import sqltypes
# TODO: clean up redunant types
# TODO: check render_bind_cast options


class FirebirdString(sqltypes.String):
    pass


class FirebirdCHARACTER(sqltypes.CHAR):
    __visit_name__ = "CHARACTER"


class FirebirdBINARY(sqltypes.BINARY):
    # charset OCTETS
    pass


class FirebirdNCHAR(sqltypes.NCHAR):
    # charset ISO8859_1
    pass


class FirebirdVARCHAR(sqltypes.VARCHAR):
    pass


class FirebirdVARBINARY(sqltypes.VARBINARY):
    # charset OCTETS
    pass


class FirebirdNVARCHAR(sqltypes.NVARCHAR):
    # charset ISO8859_1
    pass


class FirebirdNumeric(sqltypes.Numeric):
    pass


class FirebirdFLOAT(sqltypes.FLOAT):
    pass


class FirebirdDOUBLE_PRECISION(sqltypes.DOUBLE_PRECISION):
    pass


class FirebirdDECFLOAT(FirebirdNumeric):
    __visit_name__ = "DECFLOAT"


class FirebirdREAL(sqltypes.REAL):
    pass


class FirebirdDECIMAL(sqltypes.DECIMAL):
    pass


class FirebirdDATE(sqltypes.DATE):
    pass


class FirebirdTIME(sqltypes.TIME):
    pass


class FirebirdTIMESTAMP(sqltypes.TIMESTAMP):
    pass


class FirebirdInteger(sqltypes.Integer):
    render_bind_cast = True


class FirebirdSMALLINT(sqltypes.SMALLINT):
    pass


class FirebirdINTEGER(sqltypes.INTEGER):
    pass


class FirebirdBIGINT(sqltypes.BIGINT):
    pass


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


class FirebirdNumericInterval(sqltypes.Numeric):
    # NUMERIC(18,9)
    pass


# TODO datetime
# TODO json
# TODO uuid
# TODO interval ?
# TODO: array
