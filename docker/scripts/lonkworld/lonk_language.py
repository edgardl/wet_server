"""Python-callable bridge to the language procedures authored in LonkWorld.xc."""

def __getattr__(name):
    if name.startswith('__'):
        raise AttributeError(name)
    def invoke(first, *args, **kwargs):
        world = first if hasattr(first, 'controller') else first.world
        return getattr(world.controller.procedures.namespaces['language'], name)(first, *args, **kwargs)
    return invoke

def initial_language(controller):
    return controller.procedures.namespaces['language'].initial_language()
