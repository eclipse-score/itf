def py_itf_plugin(py_library, enabled_plugins, args, data, data_as_exec, tags):
    return struct(
        py_library = py_library,
        enabled_plugins = enabled_plugins,
        args = args,
        data = data,
        data_as_exec = data_as_exec,
        tags = tags,
    )
