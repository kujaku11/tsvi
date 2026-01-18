import holoviews as hv
import hvplot
import panel as pn
import numpy as np

import h5py
from mth5.mth5 import MTH5

# Threshold for enabling datashader
DATASHADE_THRESHOLD = 200_000


def cpu_usage_widget():
    cpu_usage = pn.indicators.Number(
        name="CPU",
        value=0,
        format="{value}%",
        colors=[(50, "green"), (75, "orange"), (100, "red")],
        font_size="13pt",
        title_size="8pt",
        width=50,
    )
    return cpu_usage


def memory_usage_widget():
    memory_usage = pn.indicators.Number(
        name="Memory",
        value=0,
        format="{value}%",
        colors=[(50, "green"), (75, "orange"), (100, "red")],
        font_size="13pt",
        title_size="8pt",
        width=50,
    )
    return memory_usage


def list_h5s_to_plot(channels_list):
    """

    Parameters
    ----------
    channels_list: string representation of the data paths associated with channels

    Returns
    -------
    used_files: list
        Each element of the list is the name of an mth5 file that is associated with
        at least one channel in the list.

    """
    used_files = []
    for selected_channel in channels_list:
        file_name = selected_channel.split("/")[0]
        if file_name not in used_files:
            used_files.append(file_name)
    return used_files


def channel_summary_columns_to_display():
    # Configure the displayed columns in the Channels Tab
    displayed_columns = [
        "survey",
        "station",
        "run",
        # "latitude", "longitude", "elevation",
        "component",
        "start",
        "end",
        "n_samples",
        "sample_rate",
        "measurement_type",
        # "azimuth", "tilt",
        # "units"
    ]
    return displayed_columns


# def plot_bokeh(xarray, shaded = False, shared = False):
#     plot = xarray.hvplot(
#                           width = 900,
#                           height = 450,
#                           datashade = shaded,
#                           shared_axes = shared
#                          )
#     return plot
def get_templates_dict():
    """
     Make template choice dictionary
     More information about template choices and functionality is here:
     https://panel.holoviz.org/user_guide/Templates.html
     Returns
     templates: dict

    -------

    """
    templates = {}
    templates["bootstrap"] = pn.template.BootstrapTemplate
    templates["fast"] = pn.template.FastListTemplate
    templates["golden"] = pn.template.GoldenTemplate
    templates["grid"] = pn.template.FastGridTemplate
    return templates


def invert(event, data):
    data = -1 * data
    return data

    # def get_card_controls():
    # THe idea here is to track the buttons /widgets that we want beside the plot
    #     annotate_button = pn.widgets.Button(name = "Annotate", button_type = "primary", width = 100)
    #     invert_button = pn.widgets.Button(name = "Invert", button_type = "primary", width = 100)
    #     # def invert(self, *args, **params):
    #     #   data = -1 * data
    #     # invert_button.on_click(invert(event, data))
    #     controls = pn.Column(annotate_button,
    #                          invert_button,
    #                          sizing_mode = "fixed", width = 200,)
    #     return controls


def make_plots(obj):
    """
    Build vertically stacked, shared-axis time-series subplots.
    Datashader is OFF by default, but automatically enabled for large datasets.
    No reactive wrapper is used.
    """

    hv.output(backend=obj.plotting_library.value)

    data_dict = get_mth5_data_as_xarrays(obj.selected_channels)
    panes = []

    for idx, (selected_channel, data) in enumerate(data_dict.items()):

        # Optional preprocessing
        if obj.subtract_mean_checkbox.value:
            data = data - data.mean()

        # Decide whether to use datashader
        use_datashader = len(data) > DATASHADE_THRESHOLD

        # hvPlot callable
        plot_fn = hvplot.hvPlot(
            data,
            height=obj.plot_height,
            cmap=obj.colormap,
            ylabel=data.units,
            title=selected_channel,
            responsive=True,
            max_width=obj.plot_max_width,
        )

        # Store callable for external use
        obj.plots[selected_channel] = plot_fn

        # Build the actual plot
        if use_datashader:
            curve = plot_fn(datashade=True, shared_axes=True)
        else:
            curve = plot_fn(shared_axes=True)

        # Apply axis visibility
        curve = curve.opts(
            # xaxis=xaxis_opt,
            show_grid=True,
            gridstyle={"grid_line_color": "lightgray", "grid_line_alpha": 0.5},
            xticks=20,
        )

        # Hide x-labels for all but the last subplot
        if idx < len(data_dict) - 1:
            curve = curve.opts(xlabel="")

        # Wrap in a Panel pane
        pane = pn.pane.HoloViews(
            curve, sizing_mode="stretch_width", max_width=obj.plot_max_width
        )
        panes.append(pane)

    # Stack all plots vertically
    column = pn.Column(
        *panes, sizing_mode="stretch_width", margin=0, max_width=obj.plot_max_width
    )
    # Wrap in a card
    obj.plot_cards = [
        pn.Card(
            column,
            title="Channel Subplots",
            sizing_mode="stretch_width",
            max_width=obj.plot_max_width,
        )
    ]


def get_mth5_data_as_xarrays(selected_channels):
    """
    Updated to use MTH5 context manager and selected channels dict
    is now keyed by filename and values are list of HDF5 path to the
    channel data.

    Parameters
    ----------
    selected_channels: dict
        Dictionary where keys are filenames and values are lists of HDF5 paths to the
        channel data.

    Returns
    -------

    """
    out_dict = {}
    for mth5_fn, channels in selected_channels.items():
        with MTH5() as m:

            m.open_mth5(mth5_fn, mode="r")
            for hdf5_path in channels:
                # hdf5_path is the string path to the channel (e.g., '/station/run/channel')
                ch = m.from_reference(hdf5_path)
                data = ch.to_channel_ts().to_xarray()
                ch_key = f"{ch.station_metadata.id}.{ch.run_metadata.id}.{ch.metadata.component}"
                out_dict[ch_key] = data

    return out_dict
