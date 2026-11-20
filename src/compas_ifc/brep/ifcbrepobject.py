try:
    import numpy as np
    from compas.colors import Color
    from compas.geometry import Brep
    from compas_viewer.scene.brepobject import BRepObject

    class IFCBrepObject(BRepObject):
        """Viewer object of a BRep loaded from IFC, with one colour per shell.

        Without ``shellcolors`` it is the ``BRepObject`` of compas_viewer.
        """

        def __init__(self, shellcolors=None, **kwargs):
            super().__init__(**kwargs)
            self.shellcolors = shellcolors

        @property
        def brep(self) -> Brep:
            return self.item

        def _shell_buffers(self, reverse=False):
            positions = []
            elements = []
            colors = []
            for shell, color in zip(self.brep.shells, self.shellcolors):
                tessellation = shell.to_tessellation()
                offset = len(positions)
                triangles = np.asarray(tessellation.triangles, dtype=int).reshape(-1, 3)
                if len(triangles) == 0:
                    continue
                if reverse:
                    triangles = triangles[:, ::-1]
                vertices = np.asarray(tessellation.vertices, dtype=float).reshape(-1, 3).tolist()
                positions += vertices
                elements += (triangles + offset).tolist()
                colors += [Color(*color)] * len(vertices)
                if color[3] < 1:
                    self.opacity = 0.999  # NOTE: this is to trigger the object order sorting
            return positions, colors, elements

        def _read_frontfaces_data(self):
            if not self.shellcolors:
                return super()._read_frontfaces_data()
            return self._shell_buffers()

        def _read_backfaces_data(self):
            if not self.shellcolors:
                return super()._read_backfaces_data()
            return self._shell_buffers(reverse=True)

except ImportError:
    pass
