import panel as pn
import param
from tsviewer.core import get_global_config, get_datasources
from tsviewer.datasources.tables import TableConfig

class SyntheticDataSource(param.Parameterized):

    global_config = param.ClassSelector(
        param.Parameterized, get_global_config(), instantiate=False, precedence=-1
    )
    datasources = param.ClassSelector(
        param.Parameterized, get_datasources(), instantiate=False, precedence=-1,

    )

    def dataframe(self):
        pass

