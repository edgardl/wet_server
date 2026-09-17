"""Python-callable bridge to the society procedures authored in LonkWorld.xc."""

def __getattr__(name):
    if name.startswith('__'):
        raise AttributeError(name)
    def invoke(first, *args, **kwargs):
        world = first if hasattr(first, 'controller') else first.world
        return getattr(world.controller.procedures.namespaces['society'], name)(first, *args, **kwargs)
    return invoke
