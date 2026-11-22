# Trail data editing and export plan

1. **Accept and save edits.** Start with trail segments and trailheads. Let editors add a feature or propose changes to its geometry and attributes. Save each proposal in a shared store with a stable feature ID, the original version, the proposed change, and its source. Preserve the imported data.
2. **Review changes.** Show the original and proposed versions on the comparison map. A reviewer can approve a revision, request changes, or reject it. Later edits require a fresh review.
3. **Choose features for export.** From approved revisions, filter by feature type, trail status (existing or planned), and destination. Check source permissions for that destination. Let the reviewer select individual features and preview the exact export set.
4. **Generate and record exports.** For OpenStreetMap, match features to existing OSM objects and prepare proposed edits for manual review in an OSM editor. For Google My Maps, generate a KML file. Record the destination and feature revisions in each export so reviewers can identify later changes.

First milestone: save one trailhead correction, reload it, approve it, and export it to KML. Then add trail segments and the OSM review workflow.

## Schuylkill River Water Trail (SRWT)

Offer SRT and SRWT as track choices. Use the SRG river line for the map scrubber and tag take-outs and put-ins by dam. Show a carry path only after its course is verified. The initial extract includes the river and paired endpoints at Auburn, Kernsville, and Flat Rock. Check additional sites against the section guides and confirm reuse terms before export. [SRG water trail map](https://schuylkillriver.org/trailpress/schuylkill-river/) · [Section guides and access plan](https://schuylkillriver.org/schuylkill-river-watertrail/)
