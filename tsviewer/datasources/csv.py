import panel as pn
import param
from typing import Optional, Union, List, Dict
import polars
from functools import partial
from tsviewer.core import get_global_config, get_datasources
from tsviewer.datasources.tables import TableConfig
import tempfile


class CSVDataSource(param.Parameterized):

    upload = pn.widgets.FileInput(accept=".csv", multiple=False)

    file: str = param.Filename(precedence=-1)
    has_header: bool = param.Boolean(True)
    sep: str = param.String(",")
    comment_char: Optional[str] = param.String(None)
    quote_char: Optional[str] = param.String('"')
    skip_rows: int = param.Integer(0, bounds=(0, None))
    # dtypes: Optional[Dict[str, Type[polars.datatypes.DataType]]] = param.ObjectSelector()
    null_values: Union[str, List[str], Dict[str, str]] = param.List(
        default=None, class_=str
    )
    ignore_errors: bool = param.Boolean(True)
    # cache: bool = param.Boolean(True)
    # with_column_names: Optional[Callable[[List[str]], List[str]]] = param.List(class_=str)
    infer_schema_length: Optional[int] = param.Integer(100, bounds=(0, None))
    n_rows: Optional[int] = param.Integer(None)
    encoding: str = param.String("utf8")
    low_memory: bool = param.Boolean(False)
    rechunk: bool = param.Boolean(True)
    skip_rows_after_header: int = param.Integer(0)
    parse_dates: bool = param.Boolean(True)

    global_config = param.ClassSelector(
        param.Parameterized, get_global_config(), instantiate=False, precedence=-1
    )
    datasources = param.ClassSelector(
        param.Parameterized, get_datasources(), instantiate=False, precedence=-1,

    )

    dataset_config = param.ClassSelector(
        param.Parameterized,
        TableConfig.from_dtype_dict({}),
        instantiate=True,
        precedence=-1,
    )

    lazyframe = None

    _depends = param.depends(
        "file",
        "has_header",
        "sep",
        "comment_char",
        "quote_char",
        "skip_rows",
        "null_values",
        "ignore_errors",
        "infer_schema_length",
        "n_rows",
        "encoding",
        "low_memory",
        "rechunk",
        "skip_rows_after_header",
        "parse_dates",
        watch=True,
    )

    @param.depends("upload.filename", watch=True)
    def handle_upload(self):
        tmpfile = tempfile.mktemp(suffix=".csv", prefix="tsvi-")
        with open(tmpfile, mode="wb") as f:
            f.write(self.upload.value)
        self.file = tmpfile

    @_depends
    def _lazyframe(self):
        if self.file:
            kwgs = self.param.values()
            kwgs.pop("datasources")
            kwgs.pop("global_config")
            kwgs.pop("name")
            kwgs.pop("dataset_config")
            self.lazyframe = partial(polars.scan_csv, **kwgs)
            lazyframe = self.lazyframe()
            self.dtypes = dict(
                zip(
                    lazyframe.columns,
                    map(lambda dt: dt.__name__, lazyframe.fetch().dtypes),
                )
            )
            self.dataset_config.value = TableConfig.dtype_dict_to_df(self.dtypes)
        #             print(1)
        # self.lazyframe = partial(polars.DataFrame, columns=self.with_column_names).lazy()
        else:
            self.lazyframe = None

    #         print(1)

    def datatypes_pane(self):
        return pn.FlexBox(
            pn.pane.Markdown("#### DataTypes"),
            *[pn.widgets.StaticText(name=k, value=v) for k, v in self.dtypes.items()],
            flex_direction="column",
            align_items="flex-end",
        )

    def load_options_pane(self):
        return pn.WidgetBox(
            *[self.upload, *pn.panel(self)],
        )

    @param.depends("_lazyframe")
    def view(self):
        return pn.FlexBox(
            self.load_options_pane(),
            self.dataset_config,
            flex_direction="row",
            flex_wrap='nowrap'
        )
