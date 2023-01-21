import polars
from typing import List
# Polar related functions

def _empty_lazyframe():
    return polars.DataFrame().lazy()

def get_polar_datatypes() -> List[polars.datatypes.DataType]:
    return polars.datatypes.DataType.__subclasses__()

def get_polar_datatype_names() -> List[str]:
    return [d.__name__ for d in polars.datatypes.DataType.__subclasses__()]
