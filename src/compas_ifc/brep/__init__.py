from .tessellatedbrep import TessellatedBrep

try:
    from .tessellatedbrepobject import TessellatedBrepObject
except Exception:
    pass

from compas.plugins import plugin
from compas.scene import register


# Lower priority than compas_viewer: its own registrations run first, so these are the ones kept.
@plugin(category="factories", requires=["compas_viewer"], priority=-1)
def register_scene_objects():
    register(TessellatedBrep, TessellatedBrepObject, context="Viewer")

    try:
        from compas.geometry import Brep
        from .ifcbrepobject import IFCBrepObject

        register(Brep, IFCBrepObject, context="Viewer")

    except ImportError:
        pass


__all__ = ["TessellatedBrep", "TessellatedBrepObject"]
