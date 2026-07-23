# SRG data deliveries

Source files supplied by Schuylkill River Greenways. These files are organized
by dataset year and purpose; filenames inside each delivery are preserved.

## `2025-alignment`

The supplied 2025 SRT alignment:

- existing off-road
- existing on-road
- planned off-road
- planned on-road

The four KML files contain usable geometry and attributes. They are the most
portable files in the delivery, although each uses an undeclared `xsi`
namespace and must be repaired or parsed permissively.

The `.lyrx`, `.lpkx`, `.mpkx`, and `.mxd` files preserve ArcGIS layer or map
configuration but do not embed the referenced source geodatabase. Their primary
alignment sources are feature classes with `2020` in their internal names, so
source confirmation is still needed that these files are the authoritative
2025 alignment.

## `2025-mileage-measurements`

Supporting alignment and measurement exports:

- one multipart measurement alignment
- 0.10-mile points from mile 0.0 through 123.2
- 0.25-mile points from mile 0.0 through 71.0
- one selected trailhead station point

The 0.10-mile series covers the supplied route. The 0.25-mile export is partial,
and its final 70.75 and 71.0 points do not lie on the supplied measurement
alignment.

## `2020-sign-inventory`

The 2020 inventory contains 584 point geometries and 584 matching attribute
records. Its fields are `OBJECTID`, `GlobalID`, `Sign_ID`, and `Descriptio`.
The descriptions include inventoried mileage-marker signs as well as directional,
regulatory, warning, and sponsor signs.

The source coordinate system is NAD 1983 StatePlane Pennsylvania South,
US survey feet, and the DBF encoding is UTF-8.

`Signs2020.shx` was not included in the delivery. The `.shp` is internally
complete and the missing index can be regenerated, but some shapefile readers
will require that step. The `arcgis-layer-package` directory contains the
separately supplied layer definition and package metadata; it does not contain
another copy of the sign features.

## `2024-readopt-sponsor-trail-lists`

Four zipped shapefile exports dated April 2024:

- existing off-road: 12 line records
- existing on-road: 2 line records
- planned off-road: 17 line records
- planned on-road: 16 line records

These are partial legacy/supporting trail-list layers, not replacements for the
full 2025 alignment.
