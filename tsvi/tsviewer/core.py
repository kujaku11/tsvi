import panel as pn
import param
from typing import Optional, Dict, List
import psutil
import tempfile
from loguru import logger
from cytoolz import memoize
import pandas as pd


def get_global_config() -> "GlobalConfig":
    return pn.state.as_cached("global_config", GlobalConfig)


def global_view() -> "GlobalView":
    return pn.state.as_cached("global_dashboard", GlobalView)


def get_datasources() -> "GlobalDataSources":
    return pn.state.as_cached("global_datasources", GlobalDataSources)


class GlobalConfig(param.Parameterized):
    """
    This class is a Parameterized class responsible for holding
    global variables that would require most of the other components to
    react from their changes.
    """

    title = param.String(default="Timeseries Viewer", doc="Title of the app.")

    timefilter = pn.widgets.DatetimeRangePicker(
        end=None, start=None, name="Time Filter"
    )
    timezone = pn.widgets.FloatInput(
        value=0,
        name="Timezone",
        width=75,
        start=-12,
        end=14,
        step=1,
        mode="float",
        placeholder="Select a timezone.",
    )

    # menu_items = [('Option A', 'a'), ('Option B', 'b'), None, ('Option C', 'c')]
    menu_button = pn.widgets.MenuButton(
        name="Menu",
        items=[("Dashboard", "dashboard"), ("Data Sources", "datasources")],
        height=20,
    )

    cpu_usage = pn.indicators.Number(
        name="CPU",
        value=0,
        format="{value}%",
        colors=[(50, "green"), (75, "orange"), (100, "red")],
        font_size="13pt",
        title_size="8pt",
        width=50,
    )
    memory_usage = pn.indicators.Number(
        name="Memory",
        value=0,
        format="{value}%",
        colors=[(50, "green"), (75, "orange"), (100, "red")],
        font_size="13pt",
        title_size="8pt",
        width=50,
    )

    streaming_resources = param.Boolean(default=False)

    loading_spinner = pn.indicators.LoadingSpinner(width=40, height=40)

    def __init__(self, **params):
        super().__init__(**params)
        self.start_resource_stream()

    def start_resource_stream(self):
        if self.streaming_resources:
            return

        def resouce_usage_psutil():
            return psutil.virtual_memory().percent, psutil.cpu_percent()

        def stream_resources():
            mem, cpu = resouce_usage_psutil()
            self.cpu_usage.value = cpu
            self.memory_usage.value = mem

        logger.info("Instantiating global config")
        pn.state.add_periodic_callback(stream_resources, period=1000, count=None)
        self.streaming_resources = True

    def view(self):
        return pn.FlexBox(
            self.menu_button,
            self.timefilter,
            self.timezone,
            self.cpu_usage,
            self.memory_usage,
            align_items="flex-end",
            flex_direction="row",
            flex_wrap="nowrap",
            # css_classes=['.bk panel-widget-box']
        )


class GlobalView(param.Parameterized):

    global_config = param.ClassSelector(
        param.Parameterized, get_global_config(), instantiate=False
    )
    config_layout = pn.FlexBox(flex_direction="row")
    plot_layout = pn.FlexBox(flex_direction="column")

    @property
    def config_layout(self):
        return pn.FlexBox(
            self.global_config.timefilter,
            self.global_config.timezone,
            self.global_config.loading_spinner,
            flex_direction="row",
            css_classes=[".header"],
        )

    # @param.depends(
    #     "global_config.timefilter.value", "global_config.timezone.value", watch=True
    # )
    # def test(self):
    #     print(f"global config has changed! {self.global_config.timefilter}")

    # def add_plot(self, source, variable):
    #     pass

    @param.depends("global_config.menu_button.clicked", watch=True)
    def view(self):
        clicked = self.global_config.menu_button.clicked
        pn.state.cookies["currentview"] = clicked
        if clicked == "datasources":
            return pn.panel(get_datasources().view)
        return pn.panel(clicked)


class GlobalDataSources(param.Parameterized):

    global_config = param.ClassSelector(
        param.Parameterized, get_global_config(), instantiate=False
    )
    add_datasource = pn.widgets.MenuButton(
        name="Add Data Source",
        items=[("Synthetic", "synthetic"), ("CSV", "csv"), ("Parquet", "parquet"), ("H5", "h5")],
        button_type="primary",
        height=20,
    )
    datasources = param.List()
    configuration_view = pn.FlexBox()
    current_datasources = pn.widgets.Tabulator()

    def view(self):
        return pn.FlexBox(
            self.datasources_view,
            self.add_datasource,
            pn.FlexBox(
                self.configuration_view,
                flex_direction="column"
            ),
            flex_direction="column",
        )

    # def configuration_view(self):
    #     return pn.FlexBox()

    def datasources_view(self):
        return pn.FlexBox(self.current_datasources)

    @property
    def datasources_table(self) -> 'pandas.DataFrame':
        return self.current_datasources.value

    @param.depends("add_datasource.clicked", watch=True)
    def _create_datasource(self):
        from .datasources import DATASOURCES
        clicked = self.add_datasource.clicked
        datasource_cls = DATASOURCES.get(clicked, None)
        if datasource_cls:
            datasource_instance = datasource_cls()
            self.current_datasources.value = pd.DataFrame(
                {'name': datasource_instance.name, 'type': clicked},
                index=[0])
            self.configuration_view.objects = [datasource_instance.view]
        else:
            self.configuration_view.objects = [f"Datasource '{clicked}' not implement yet."]


