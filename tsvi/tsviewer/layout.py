import panel as pn
from tsvi.tsviewer.core import get_global_config, global_view
from tsvi.tsviewer.datasources.csv import CSVDataSource

pn.extension("tabulator", notifications=True)

ds = CSVDataSource()

global_config = get_global_config()
global_view = global_view()

layout = pn.Column(
    global_config.view,
    global_view.view,
)


layout.servable()
# pn.serve(pn.Column(get_global_config().view, ds.view))
