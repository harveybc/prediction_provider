class PluginManager:
    def __init__(self):
        self._plugins = {}

    def register(self, plugin):
        if hasattr(plugin, 'name'):
            self._plugins[plugin.name] = plugin
        else:
            # Fallback for plugins without a name attribute
            self._plugins[plugin.__class__.__name__] = plugin

    def get(self, name):
        return self._plugins.get(name)
