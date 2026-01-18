import pathlib
import pandas as pd
import panel as pn
import param
import psutil
import xarray

import holoviews as hv
import hvplot.xarray

from mth5.mth5 import MTH5
from mth5 import CHANNEL_DTYPE

from tsvi.mth5_tsviewer.helpers import (
    channel_summary_columns_to_display,
    cpu_usage_widget,
    memory_usage_widget,
    make_plots,
)

hv.extension("bokeh")
xarray.set_options(keep_attrs=True)

CH_SUMMARY_DISPLAY_COLUMNS = channel_summary_columns_to_display()
COLORMAP = "Magma"


class Tsvi(param.Parameterized):

    # Resource widgets (static)
    cpu_usage = cpu_usage_widget()
    memory_usage = memory_usage_widget()

    # Parameters
    plot_width = param.Integer(default=900)
    plot_height = param.Integer(default=450)
    annotatable = param.Boolean(default=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # -------------------------
        # Template
        # -------------------------
        from tsvi.mth5_tsviewer.helpers import get_templates_dict

        template_key = "golden"
        self.template = get_templates_dict()[template_key](title="TSVI")

        # -------------------------
        # State
        # -------------------------
        self.channel_summary = pd.DataFrame(columns=CHANNEL_DTYPE.names)
        self.selected_channels = {}
        self.xarrays = []
        self.plots = {}

        # -------------------------
        # Widgets
        # -------------------------
        self.files = pn.widgets.FileInput(
            name="Select MTH5 Files",
            accept=".h5",
            multiple=True,
        )
        self.files.param.watch(self.update_channels, "value")

        self.run_or_channel_checkbox = pn.widgets.Checkbox(
            name="Pick Runs", value=False
        )

        self.clear_plots_button = pn.widgets.Button(
            name="Clear Plots", button_type="danger"
        )
        self.clear_plots_button.on_click(self.clear_plots)

        self.clear_channels_button = pn.widgets.Button(
            name="Clear Channels", button_type="danger"
        )
        self.clear_channels_button.on_click(self.clear_channels)

        self.plot_button = pn.widgets.Button(name="Plot", button_type="primary")
        self.plot_button.on_click(self.make_and_display_plots)

        self.plotting_library = pn.widgets.RadioButtonGroup(
            name="Plotting Library",
            options=["bokeh", "matplotlib"],
            button_type="primary",
            width=200,
        )

        self.subtract_mean_checkbox = pn.widgets.Checkbox(
            name="Subtract Mean", value=True
        )

        # -------------------------
        # Tabs
        # -------------------------
        self.channels_tab = self.make_channels_tab()
        self.plots_tab = self.make_plots_tab()

        self.tabs = pn.Tabs(
            ("Channels", self.channels_tab),
            ("Plots", self.plots_tab),
            dynamic=False,
        )

        # -------------------------
        # Sidebar
        # -------------------------
        self.build_sidebar()

        # -------------------------
        # Layout
        # -------------------------
        self.template.main[:] = [self.tabs]

        # -------------------------
        # Resource streaming
        # -------------------------
        self.start_resource_stream()

    # =========================================================
    # Sidebar
    # =========================================================
    def build_sidebar(self):
        self.template.sidebar[:] = [
            self.cpu_usage,
            self.memory_usage,
            pn.pane.Markdown("### Load MTH5 Files"),
            self.files,
            self.run_or_channel_checkbox,
            self.clear_plots_button,
            self.clear_channels_button,
        ]

    # =========================================================
    # Tabs
    # =========================================================
    def make_channels_tab(self):
        self.channels_table = pn.widgets.Tabulator(
            self.channel_summary[CH_SUMMARY_DISPLAY_COLUMNS],
            selectable=True,
            height=500,
        )
        self.channels_table.param.watch(self.select_channels, "selection")

        controls = pn.Column(
            self.plotting_library,
            self.subtract_mean_checkbox,
        )

        return pn.Column(
            pn.Row(self.channels_table, controls),
            self.plot_button,
        )

    def make_plots_tab(self):
        self.graphs = pn.Column(
            sizing_mode="stretch_width",
            margin=0,
            max_width=1000,
        )
        return pn.Column(self.graphs)

    # =========================================================
    # Callbacks
    # =========================================================
    def update_channels(self, event):
        print("Files uploaded event:", event.new)

        full_df = pd.DataFrame()

        # event.new is a list of bytes when multiple=True
        for i, file_bytes in enumerate(event.new):
            # Panel does NOT reliably populate filename in templates
            # So we create our own temporary file
            tmp_path = pathlib.Path(f"uploaded_{i}.h5")
            tmp_path.write_bytes(file_bytes)

            with MTH5() as m:
                m = m.open_mth5(tmp_path, mode="r")
                df = m.channel_summary.to_dataframe()
                df["file"] = str(tmp_path)
                df["hdf5_reference"] = df["hdf5_reference"].apply(
                    lambda ref: m.get_reference_path(ref)
                )
                df.drop(
                    columns=["run_hdf5_reference", "station_hdf5_reference"],
                    inplace=True,
                )

            full_df = pd.concat([full_df, df])

        self.channel_summary = full_df.reset_index(drop=True)
        self.refresh_channels_tab()
        self.tabs.active = 0

    def refresh_channels_tab(self):
        self.channels_table.value = self.channel_summary[CH_SUMMARY_DISPLAY_COLUMNS]

    def select_channels(self, event):
        self.selected_channels = {}
        if event.new:
            for idx in event.new:
                row = self.channel_summary.iloc[idx]
                self.selected_channels.setdefault(row["file"], []).append(
                    row["hdf5_reference"]
                )

    def make_and_display_plots(self, *args):
        self.tabs.active = 1
        self.make_plots()
        self.display_plots()

    def make_plots(self):
        make_plots(self)

    def display_plots(self):
        self.graphs.objects = list(self.plots.values())

    def clear_plots(self, event=None):
        self.xarrays = []
        self.plots = {}
        self.graphs.objects = []

    def clear_channels(self, event=None):
        self.selected_channels = {}
        self.channel_summary = pd.DataFrame(columns=CHANNEL_DTYPE.names)
        self.refresh_channels_tab()

    # =========================================================
    # Resource Streaming
    # =========================================================
    def start_resource_stream(self):
        def update_resources():
            mem = psutil.virtual_memory().percent
            cpu = psutil.cpu_percent()
            self.cpu_usage.value = cpu
            self.memory_usage.value = mem

        pn.state.add_periodic_callback(update_resources, period=1000)

    # =========================================================
    # Entry Point
    # =========================================================
    def view(self):
        return self.template


tsvi = Tsvi(plot_width=700, plot_height=200)
tsvi.template.servable()
