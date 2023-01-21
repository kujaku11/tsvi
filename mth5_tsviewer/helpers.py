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




# def plot_bokeh(xarray, shaded = False, shared = False):
#     plot = xarray.hvplot(
#                           width = 900,
#                           height = 450,
#                           datashade = shaded,
#                           shared_axes = shared
#                          )
#     return plot