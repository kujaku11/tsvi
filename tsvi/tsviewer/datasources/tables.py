import pandas as pd
import panel as pn
import param
from bokeh.models.widgets.tables import SelectEditor, BooleanFormatter
from tsviewer.datasources.polarutils import get_polar_datatype_names


class TableConfig(pn.widgets.Tabulator):
    """
    If dataset is a table-like dataset, we use this class to config.
    """

    editors = {
        "DataType": SelectEditor(options=get_polar_datatype_names()),
    }
    formatters = {
        "DateTimeColumn": BooleanFormatter(),
    }
    layout='fit_columns'
    width=650
    header_filters = True
    selectable = "checkbox"
    text_align = "center"

    @classmethod
    def from_dtype_dict(cls, dtypes: dict[str, str]):
        return cls(value=cls.dtype_dict_to_df(dtypes))

    @classmethod
    def dtype_dict_to_df(cls, dtypes: dict[str, str]):
        df = pd.DataFrame.from_dict(dtypes, orient="index", columns=["DataType"])
        df["DateTimeColumn"] = False
        return df
