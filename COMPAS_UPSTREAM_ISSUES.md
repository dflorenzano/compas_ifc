# COMPAS upstream API inconsistencies affecting compas_ifc

Known API mismatches in `compas`, `compas_model`, and the `compas.geometry`
type hierarchy that `compas_ifc` has to work around. All discovered during
clash-detection work on the duplex model. Worth filing upstream issues.

## 1. `Mesh.aabb` / `Mesh.obb` are methods, not properties

**Fixed in COMPAS 3:** both are properties there. The text below describes COMPAS 2.

- `compas.datastructures.Mesh.aabb` is defined as `def aabb(self)` —
  accessing `mesh.aabb` returns a bound method, not a `Box`.
- `compas.geometry.Geometry.aabb` (Brep, Extrusion, Polyhedron, …) is a
  `@property` that lazily calls `compute_aabb()`.
- Any code that does `hasattr(g, "aabb")` + `g.aabb` silently breaks on
  `Mesh` inputs — stores the bound method on caches like `Element._aabb`
  and crashes later (`'function' object has no attribute 'frame'`).

## 2. `compute_aabb` signature mismatch

- `compas_model.models.bvh.ElementBVH.nearest_neighbors` calls
  `element.compute_aabb(inflate=1.2)`.
- `compas_model.elements.Element.compute_aabb(inflate=1.0)` accepts the kwarg.
- `compas.geometry.Geometry.compute_aabb()` does **not**.
- Subclasses that forward to `geom.compute_aabb()` silently drop the
  inflate — broadphase ends up not inflating at all.

## 3. `Geometry` subclasses inherit `aabb` without implementing `compute_aabb`

- `Geometry.aabb` is a property that calls `self.compute_aabb()`, which
  itself raises `NotImplementedError` in the base.
- Any subclass that forgets to override `compute_aabb` will raise on
  attribute access of `.aabb`, not at class-definition time.
- `compas_ifc`'s `ClippedExtrusion` had this — fixed locally by
  delegating to the base extrusion (half-space clipping only removes
  material, so the inner extrusion's AABB is a valid conservative bound).

## 4. `Extrusion.transform()` is a no-op on profile points

- `Geometry.transformed(t)` does `.copy(); .transform(t)`. For `Mesh`,
  that transforms every vertex. For `compas_ifc.representations.Extrusion`
  (and by extension `ClippedExtrusion`), `transform()` only updates
  `self.frame`. `_profile_points()` returns local-frame points regardless.
- Effect: `compute_aabb()` / `to_mesh()` always return local-frame geometry.
  `compas_model.Element.compute_modelgeometry()` (which does
  `self.elementgeometry.transformed(modeltransformation)`) silently
  produces local-frame meshes for any Extrusion-backed element.
- That's catastrophic for collision/contact detection: pairs of Extrusion
  elements get tested against each other in their respective local frames
  (or never tested at all, if narrowphase short-circuits on non-Mesh types).
- **Workaround in `compas_ifc`:** `GenericElement._world_mesh()` always
  builds the world-coord mesh as
  `visual_geometry.to_mesh().transformed(modeltransformation)`.
  `compute_aabb`, `compute_obb`, `compute_collisions`, `compute_contacts`
  all go through it.

## How to apply these in compas_ifc

- When consuming `geom.aabb` / `geom.obb` from arbitrary geometry,
  check `isinstance(geom, Mesh)` explicitly **or** use
  `aabb() if callable(aabb) else aabb`. Don't trust `hasattr(g, "aabb")` alone.
- When adding new `Geometry` subclasses, always implement `compute_aabb`
  (and `compute_obb`) — even a conservative bound delegated to a wrapped
  subgeometry is better than `NotImplementedError`.
- For anything geometry-in-world-space (clash detection, contact
  detection, BVH spatial indexing), go through `GenericElement._world_mesh()`
  rather than `element.model_geometry` (`modelgeometry` before the COMPAS 3
  version of `compas_model`).

## Upstream fixes worth proposing

- Make `Mesh.aabb` / `Mesh.obb` properties in `compas.datastructures.Mesh`
  (done in COMPAS 3).
- Align `compute_aabb` signatures between `compas.geometry.Geometry` and
  `compas_model.elements.Element` (either both accept `inflate`, or neither).
- Fix `Extrusion.transform()` (or whichever upstream class this maps to)
  to transform the profile points, not just the frame — so that
  `Geometry.transformed()` behaves consistently across all subclasses.

### Differences found in the port to COMPAS 3

Found on `compas` `remove-future` @ `99b82a6`, `compas_model` `c3-upgrade` @
`83df416` and `compas_occ` `c3-upgrade` @ `7fdf2ff`. They are changes of
behaviour, not all of them defects.

- **`OCCBrepEdge.first_vertex`, `last_vertex` and `to_line()` follow the
  orientation of the edge in its loop** (`TopExp.FirstVertex(edge, True)`).
  `compas_occ` 1.5 gave the direction of the curve. The IFC export needs the
  curve direction and reads it from OCC (`_edge_start`, `_edge_end` in
  `conversions/brep.py`).
- **`compas_occ.brep.OCCBrep` is not a `compas.geometry.Brep`.** Type checks
  in `compas_model` (modifiers, `is_geometry_empty`) reject it; build B-Reps
  with `Brep.from_native`, `Brep.from_step`, …
- **`ElementBVH.nearby_elements(element, tolerance)` takes an absolute
  distance;** `nearest_neighbors` of `compas_model` 0.9 inflated the box by a
  factor 1.2. With tolerance 0, touching neighbours are missed (63 of 99 wall
  connections on the Duplex). `compas_ifc` passes 10 % of the largest box side.
- **`Data.name` is `''` for an empty name;** COMPAS 2 returned the class name.
- **`Color` rejects NaN components;** a material without a diffuse colour
  gives NaN face colours, which the viewer object replaces by grey.
- **`compas_model` has no public way to add a custom interaction record**
  (`_add_interaction_record` is private). IFC relationships therefore stay
  dictionaries on the graph edges.
