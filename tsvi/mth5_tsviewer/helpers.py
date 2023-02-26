import holoviews as hv
import hvplot
import panel as pn

from mth5.mth5 import MTH5

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
    Gets the data and plots it.

    ToDo: Factor into
    - get data
    - preprocess
    - plot data

    takes a list of mth5 files and then it converts that list to channels,
    it needs to know what channels were used (self.cahnnels


    Parameters
    ----------
    obj: __main__.Tsvi object


    """
    hv.output(backend = obj.plotting_library.value)
    new_cards  = []
    used_files = list_h5s_to_plot(obj.channels.value)

    # data_dict = preprocess(data_dict, obj.subtract_mean_checkbox.value)
    # plot_cards = make_plots(data_dict)

    # Keyed with the selected_channel from below
    data_dict = get_mth5_data_as_xarrays(obj.channels.value, obj.file_paths)
    # data_dict = preprocess(data_dict, obj.subtract_mean_checkbox.value)
    # plot_cards = make_plots(data_dict)
    # from holoviews.operation.datashader import datashade
    for selected_channel,data in data_dict.items():
        selected_file, station, run, channel = selected_channel.split("/")
        ylabel = data.type
        if obj.subtract_mean_checkbox.value == True:
            data = data - data.mean()
            plot = hvplot.hvPlot(data,
                                 width = obj.plot_width,
                                 height = obj.plot_height,
                                 cmap = obj.colormap,
                                 ylabel = ylabel)
            #plot = datashade(hv.Curve(data))
            obj.plots[selected_channel] = plot
            if obj.plotting_library.value == "bokeh":
                bound_plot = pn.bind(plot,
                                     datashade = obj.datashade_checkbox,
                                     shared_axes = obj.shared_axes_checkbox)

            elif obj.plotting_library.value == "matplotlib":
                fig = Figure(figsize = (8,6))

            invert_button = pn.widgets.Button(name="Invert", button_type="primary", width=100)

            # invert_button.on_click(invert(event, data))
            controls = pn.Column(
                invert_button,
                sizing_mode = "fixed", width = 200,)
            plot_pane = pn.Pane(bound_plot)
            plot_tab = pn.Row(plot_pane,
                              controls,
                              name = run + "/" + channel)
            if obj.annotatable:
                obj.annotators[selected_channel] = hv.annotate.instance()
                note_tab = pn.Pane(obj.annotators[selected_channel].compose(plot.line(datashade=False).opts(width = 700, height = 200),
                                                                            obj.annotators[selected_channel](
                                                                                hv.Rectangles(data= []).opts(alpha=0.5),
                                                                                annotations = ["Label"],
                                                                                name = "Notes")),
                                   name = "Notes")

                tabs = pn.Tabs(plot_tab,
                               note_tab)
            else:
                tabs = pn.Tabs(plot_tab)
            new_card = pn.Card(tabs,
                               title = selected_channel)

            new_cards.append(new_card)


    obj.plot_cards = new_cards
    return


def get_mth5_data_as_xarrays(selected_channels, file_paths):
    """
    ToDo:
    - This can be modified in future to support chunking read in
    - interaction with the intake package belongs here.
    - This function works on multiple mth5 files in sequence. Another way to do this
    would to be to invert the two for loops so that the outer loop iterates over
    selected_channels first and then a one-line function accesses the data for that
    channel.

    Parameters
    ----------
    selected_channels: list
    file_paths
    kwargs

    Returns
    -------

    """
    out_dict = {}
    used_files = list_h5s_to_plot(selected_channels)
    for file in used_files:
        m = MTH5()
        m.open_mth5(file_paths[file], mode = "r")
        for selected_channel in selected_channels:
            selected_file, station, run, channel = selected_channel.split("/")
            if selected_file == file:
                data = m.get_channel(station, run, channel).to_channel_ts().to_xarray()
                # data = data.rename(data.attrs["mth5_type"]): "ex"--> "Electric"
                #self.xarrays.append(data)
                out_dict[selected_channel] = data
        m.close_mth5()
    return out_dict
