import panel as pn


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
    memory_usage= pn.indicators.Number(
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
    channels_list: string represenation of the data paths asscocated with channels
        May need to be modified to work on windows, if so, we should
        cast them to path objects and take [Path(x).name for x in channels_list]

    Returns
    -------

    """
    used_files = []
    for selected_channel in channels_list:
        file_name = selected_channel.split("/")[0]
        if file_name not in used_files:
            used_files.append(file_name)
    return used_files


def channel_summary_columns_to_display():
    # Configure the displayed columns in the Channels Tab
    displayed_columns = ["survey", "station", "run",
                         #"latitude", "longitude", "elevation",
                         "component",
                         "start", "end", "n_samples", "sample_rate",
                         "measurement_type",
                         #"azimuth", "tilt",
                         #"units"
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