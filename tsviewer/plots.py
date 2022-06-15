import param


class Plot(param.Parameterized):

    global_config = param.ClassSelector(
        param.Parameterized, get_global_config(), instantiate=False
    )
    datasources = param.ClassSelector(
        param.Parameterized, get_datasources(), instantiate=False
    )
